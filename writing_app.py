import json
import os
import time
import tkinter as tk
from tkinter import messagebox, simpledialog, filedialog

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "articles.json")

# ---------- theme ----------
BG = "#0B0B0B"            # deep black
NAVBG = "#080808"
SURFACE = "#141414"
PANEL = "#1C1C1C"
BORDER = "#262626"
NEON = "#39FF14"          # neon green
NEON_HOVER = "#6BFF4F"
TEXT = "#EDEDED"
MUTED = "#8A8A8A"
DANGER = "#FF5C5C"

# button kinds: (background, text, hover background, hover text)
KINDS = {
    "primary":   (NEON, BG, NEON_HOVER, BG),
    "secondary": (PANEL, TEXT, BORDER, NEON),
    "danger":    (PANEL, DANGER, "#2A1414", DANGER),
    "nav":       (NAVBG, MUTED, SURFACE, NEON),
}


class FlatButton(tk.Label):
    """A flat button with a hover effect (a Label, so colors work on every OS)."""

    def __init__(self, parent, text, command, kind="secondary", **kw):
        self.kind = kind
        self.command = command
        self.active = False
        options = dict(font=("Helvetica", 10, "bold"), padx=14, pady=7, cursor="hand2")
        options.update(kw)
        super().__init__(parent, text=text, bg=KINDS[kind][0], fg=KINDS[kind][1], **options)
        self.bind("<Enter>", lambda e: self.paint(True))
        self.bind("<Leave>", lambda e: self.paint(False))
        self.bind("<Button-1>", lambda e: self.command())

    def paint(self, hover):
        bg, fg, hover_bg, hover_fg = KINDS[self.kind]
        if hover or self.active:
            bg, fg = hover_bg, hover_fg
        self.config(bg=bg, fg=fg)

    def set_active(self, on):
        self.active = on
        self.paint(False)


def make_list(parent, **kw):
    return tk.Listbox(parent, bg=SURFACE, fg=TEXT, selectbackground=NEON,
                      selectforeground=BG, relief="flat", bd=0, activestyle="none",
                      highlightthickness=1, highlightbackground=BORDER,
                      highlightcolor=NEON, font=("Helvetica", 11),
                      exportselection=False, **kw)


def make_scrollbar(parent, command):
    return tk.Scrollbar(parent, command=command, bg=BORDER, troughcolor=SURFACE,
                        activebackground=NEON, relief="flat", bd=0,
                        highlightthickness=0, width=10)


def page_header(parent, title, subtitle=""):
    tk.Label(parent, text=title, bg=BG, fg=TEXT,
             font=("Helvetica", 22, "bold")).pack(anchor="w")
    tk.Frame(parent, bg=NEON, height=3, width=48).pack(anchor="w", pady=(6, 6))
    if subtitle:
        tk.Label(parent, text=subtitle, bg=BG, fg=MUTED).pack(anchor="w", pady=(0, 8))


def word_count(text):
    return len(text.split())


def on_item(listbox, event):
    """True only if the click landed on a real row (not on the blank space below)."""
    box = listbox.bbox(listbox.nearest(event.y))
    return bool(box) and box[1] <= event.y <= box[1] + box[3]


AUTOSAVE_MS = 30000     # autosave every 30 seconds


class WritingApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Quillian")
        self.geometry("1000x620")
        self.minsize(800, 500)
        self.configure(bg=BG)

        self.startup_warning = None
        self.articles = self.load_data()
        self.last_saved = self.serialize()   # what is currently on disk
        self.current = None        # the article being edited
        self.sec_index = None      # index of the section shown in the editor

        # status bar is packed first so it always stays visible at the bottom
        self.status = tk.StringVar(value="Welcome!")
        tk.Label(self, textvariable=self.status, anchor="w", bg=NAVBG, fg=MUTED,
                 padx=12, pady=5, font=("Helvetica", 9)).pack(side="bottom", fill="x")

        self.build_nav()
        self.build_dashboard()
        self.build_drafts()
        self.build_archive()
        self.build_editor()

        self.show("dashboard")
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(AUTOSAVE_MS, self.autosave)
        if self.startup_warning:
            messagebox.showwarning("Quillian", self.startup_warning)

    # ---------- data ----------
    def load_data(self):
        if not os.path.exists(DATA_FILE):
            return []
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                raise ValueError("articles file is not a list")
            return data
        except (ValueError, OSError):
            # Never overwrite a damaged file: keep a copy of it first.
            backup = DATA_FILE.replace(".json", f".damaged-{time.strftime('%Y%m%d-%H%M%S')}.json")
            try:
                os.replace(DATA_FILE, backup)
                self.startup_warning = ("Your articles file could not be read.\n"
                                        f"A copy was kept as:\n{backup}\n\nStarting empty.")
            except OSError:
                self.startup_warning = ("Your articles file could not be read, and a backup "
                                        "copy could not be made. Saving is disabled to protect it.")
                self.saving_disabled = True
            return []

    saving_disabled = False

    def serialize(self):
        return json.dumps(self.articles, indent=2)

    def save_data(self, quiet=False):
        """Write all articles safely (temp file, then swap). Returns True on success."""
        if self.saving_disabled:
            return False
        text = self.serialize()
        tmp = DATA_FILE + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(text)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, DATA_FILE)
        except OSError as err:
            if not quiet:
                messagebox.showerror("Could not save", f"Your work was NOT saved:\n{err}")
            self.status.set("Could not save! Check the folder is writable.")
            return False
        self.last_saved = text
        return True

    def autosave(self):
        """Every few seconds, write any unsaved changes to disk."""
        try:
            if self.current is not None:
                self.store_editor()
                if self.serialize() != self.last_saved:
                    self.current["updated"] = self.now()
                    if self.save_data(quiet=True):
                        self.status.set(f"Autosaved at {time.strftime('%H:%M:%S')}")
        finally:
            self.after(AUTOSAVE_MS, self.autosave)

    def article_words(self, article):
        return sum(word_count(s["text"]) for s in article["sections"])

    def active_articles(self):
        return [a for a in self.articles if not a.get("archived", False)]

    def archived_articles(self):
        return [a for a in self.articles if a.get("archived", False)]

    def now(self):
        return time.strftime("%Y-%m-%d %H:%M")

    # ---------- navigation ----------
    def build_nav(self):
        nav = tk.Frame(self, bg=NAVBG, width=200)
        nav.pack(side="left", fill="y")
        nav.pack_propagate(False)
        tk.Frame(self, bg=NEON, width=1).pack(side="left", fill="y")   # thin neon edge

        tk.Label(nav, text="QUILLIAN", bg=NAVBG, fg=NEON,
                 font=("Helvetica", 18, "bold")).pack(pady=(24, 0))
        tk.Label(nav, text="writing studio", bg=NAVBG, fg=MUTED,
                 font=("Helvetica", 9)).pack(pady=(0, 24))

        self.nav_buttons = {}
        for name, text in [("dashboard", "Dashboard"), ("drafts", "Drafts"),
                           ("archive", "Archive")]:
            btn = FlatButton(nav, text, lambda n=name: self.show(n), "nav",
                             anchor="w", padx=24, pady=10)
            btn.pack(fill="x", pady=1)
            self.nav_buttons[name] = btn

        self.content = tk.Frame(self, bg=BG)
        self.content.pack(side="right", fill="both", expand=True)

    def show(self, name):
        if name != "editor":
            self.store_editor()
        self.frames = {"dashboard": self.dash_frame,
                       "drafts": self.drafts_frame,
                       "archive": self.archive_frame,
                       "editor": self.editor_frame}
        for f in self.frames.values():
            f.pack_forget()
        if name == "dashboard":
            self.refresh_dashboard()
        elif name == "drafts":
            self.refresh_drafts()
        elif name == "archive":
            self.refresh_archive()
        self.frames[name].pack(fill="both", expand=True)

        highlight = name if name in self.nav_buttons else "drafts"   # editor belongs to Drafts
        for key, btn in self.nav_buttons.items():
            btn.set_active(key == highlight)

    # ---------- dashboard ----------
    def build_dashboard(self):
        self.dash_frame = tk.Frame(self.content, bg=BG, padx=28, pady=24)
        page_header(self.dash_frame, "Dashboard", "Double-click a draft to keep writing.")

        self.stat_vars = {k: tk.StringVar() for k in ("drafts", "archived", "words")}
        stats = tk.Frame(self.dash_frame, bg=BG)
        stats.pack(fill="x", pady=(6, 20))
        for i, (key, label) in enumerate([("drafts", "DRAFTS"),
                                          ("archived", "ARCHIVED"),
                                          ("words", "TOTAL WORDS")]):
            stats.grid_columnconfigure(i, weight=1, uniform="stat")
            box = tk.Frame(stats, bg=SURFACE, highlightthickness=1,
                           highlightbackground=BORDER, padx=18, pady=14)
            box.grid(row=0, column=i, sticky="ew", padx=(0, 12 if i < 2 else 0))
            tk.Label(box, textvariable=self.stat_vars[key], bg=SURFACE, fg=NEON,
                     font=("Helvetica", 26, "bold")).pack(anchor="w")
            tk.Label(box, text=label, bg=SURFACE, fg=MUTED,
                     font=("Helvetica", 9, "bold")).pack(anchor="w")

        tk.Label(self.dash_frame, text="RECENTLY EDITED", bg=BG, fg=MUTED,
                 font=("Helvetica", 9, "bold")).pack(anchor="w", pady=(0, 8))
        self.recent_hint = tk.Label(self.dash_frame, bg=BG, fg=MUTED, anchor="w")
        self.recent_hint.pack(fill="x")
        self.recent_list = make_list(self.dash_frame)
        self.recent_list.pack(fill="both", expand=True)
        self.recent_list.bind("<Double-Button-1>",
                              lambda e: on_item(self.recent_list, e) and self.open_recent())

    def recent_articles(self):
        return sorted(self.active_articles(), key=lambda a: a["updated"], reverse=True)[:8]

    def refresh_dashboard(self):
        active = self.active_articles()
        self.stat_vars["drafts"].set(len(active))
        self.stat_vars["archived"].set(len(self.archived_articles()))
        self.stat_vars["words"].set(sum(self.article_words(a) for a in active))

        self.recent_list.delete(0, "end")
        for a in self.recent_articles():
            self.recent_list.insert("end", f"  {a['title']}   -   {a['updated']}")
        self.recent_hint.config(
            text="" if active else "No drafts yet. Open Drafts and press New to start writing.")

    def open_recent(self):
        sel = self.recent_list.curselection()
        if sel:
            self.open_article(self.recent_articles()[sel[0]])

    # ---------- drafts ----------
    def build_drafts(self):
        self.drafts_frame = tk.Frame(self.content, bg=BG, padx=28, pady=24)
        page_header(self.drafts_frame, "Drafts",
                    "Double-click a draft, or select it and press Editor.")

        self.drafts_hint = tk.Label(self.drafts_frame, bg=BG, fg=MUTED, anchor="w")
        self.drafts_hint.pack(fill="x")
        self.drafts_list = make_list(self.drafts_frame)
        self.drafts_list.pack(fill="both", expand=True, pady=(0, 14))
        self.drafts_list.bind("<Double-Button-1>",
                              lambda e: on_item(self.drafts_list, e) and self.open_selected_draft())

        row = tk.Frame(self.drafts_frame, bg=BG)
        row.pack(anchor="w")
        for text, cmd, kind in [("New", self.new_article, "primary"),
                                ("Editor", self.open_selected_draft, "secondary"),
                                ("Archive", self.archive_selected_article, "secondary"),
                                ("Delete", self.delete_selected_draft, "danger")]:
            FlatButton(row, text, cmd, kind).pack(side="left", padx=(0, 8))

    def refresh_drafts(self):
        self.drafts_list.delete(0, "end")
        for a in self.active_articles():
            self.drafts_list.insert(
                "end", f"  {a['title']}   -   {self.article_words(a)} words   -   {a['updated']}")
        self.drafts_hint.config(
            text="" if self.active_articles() else "No drafts yet. Press New to start writing.")

    def selected_draft(self):
        sel = self.drafts_list.curselection()
        if not sel:
            messagebox.showinfo("Select", "Select a draft first.")
            return None
        return self.active_articles()[sel[0]]

    def open_selected_draft(self):
        a = self.selected_draft()
        if a:
            self.open_article(a)

    def archive_selected_article(self):
        a = self.selected_draft()
        if a:
            self.archive_article(a)

    def delete_selected_draft(self):
        a = self.selected_draft()
        if a:
            self.delete_article(a)
            self.refresh_drafts()

    # ---------- archive ----------
    def build_archive(self):
        self.archive_frame = tk.Frame(self.content, bg=BG, padx=28, pady=24)
        page_header(self.archive_frame, "Archive",
                    "Restore a draft to bring it back to Drafts.")

        self.archive_hint = tk.Label(self.archive_frame, bg=BG, fg=MUTED, anchor="w")
        self.archive_hint.pack(fill="x")
        self.archive_list = make_list(self.archive_frame)
        self.archive_list.pack(fill="both", expand=True, pady=(0, 14))

        row = tk.Frame(self.archive_frame, bg=BG)
        row.pack(anchor="w")
        FlatButton(row, "Restore", self.restore_selected_article, "primary").pack(
            side="left", padx=(0, 8))
        FlatButton(row, "Delete", self.delete_selected_archived, "danger").pack(side="left")

    def refresh_archive(self):
        self.archive_list.delete(0, "end")
        for a in self.archived_articles():
            self.archive_list.insert(
                "end", f"  {a['title']}   -   {self.article_words(a)} words   -   {a['updated']}")
        self.archive_hint.config(
            text="" if self.archived_articles() else "The archive is empty.")

    def selected_archived(self):
        sel = self.archive_list.curselection()
        if not sel:
            messagebox.showinfo("Select", "Select an archived draft first.")
            return None
        return self.archived_articles()[sel[0]]

    def archive_article(self, article):
        self.store_editor()
        article["archived"] = True
        article["updated"] = self.now()
        if article is self.current:         # an archived draft can't stay open
            self.current = None
            self.sec_index = None
        self.save_data()
        self.status.set(f"'{article['title']}' moved to the archive.")
        self.show("archive")

    def restore_selected_article(self):
        a = self.selected_archived()
        if not a:
            return
        a["archived"] = False
        a["updated"] = self.now()
        self.save_data()
        self.status.set(f"'{a['title']}' restored to Drafts.")
        self.show("drafts")

    def delete_selected_archived(self):
        a = self.selected_archived()
        if a:
            self.delete_article(a)
            self.refresh_archive()

    def delete_article(self, article):
        """Ask for confirmation, then permanently remove an article."""
        if not messagebox.askyesno(
                "Delete", f"Are you sure you want to delete '{article['title']}'?"):
            return
        if article is self.current:
            self.current = None
            self.sec_index = None
        self.articles.remove(article)
        self.save_data()
        self.status.set("Draft deleted.")

    # ---------- editor ----------
    def build_editor(self):
        self.editor_frame = tk.Frame(self.content, bg=BG)

        # top bar: title + buttons
        top = tk.Frame(self.editor_frame, bg=SURFACE, padx=14, pady=10)
        top.pack(fill="x")
        tk.Label(top, text="TITLE", bg=SURFACE, fg=MUTED,
                 font=("Helvetica", 9, "bold")).pack(side="left")
        self.title_var = tk.StringVar()
        tk.Entry(top, textvariable=self.title_var, font=("Helvetica", 14, "bold"),
                 bg=BG, fg=TEXT, insertbackground=NEON, relief="flat",
                 highlightthickness=1, highlightbackground=BORDER,
                 highlightcolor=NEON).pack(side="left", fill="x", expand=True,
                                           padx=10, ipady=5)
        FlatButton(top, "Save", self.save_article, "primary").pack(side="left", padx=3)
        FlatButton(top, "Archive", self.archive_current_article).pack(side="left", padx=3)
        FlatButton(top, "Export .txt", self.export_article).pack(side="left", padx=3)
        tk.Frame(self.editor_frame, bg=NEON, height=1).pack(fill="x")

        body = tk.Frame(self.editor_frame, bg=BG)
        body.pack(fill="both", expand=True)

        # side panel: sections
        side = tk.Frame(body, bg=BG, padx=14, pady=12)
        side.pack(side="left", fill="y")
        tk.Label(side, text="SECTIONS", bg=BG, fg=MUTED,
                 font=("Helvetica", 9, "bold")).pack(anchor="w", pady=(0, 6))
        self.sec_list = make_list(side, width=24)
        self.sec_list.pack(fill="y", expand=True, pady=(0, 8))
        self.sec_list.bind("<<ListboxSelect>>", self.on_section_select)
        for text, cmd in [("Add Section", self.add_section),
                          ("Rename", self.rename_section),
                          ("Move Up", lambda: self.move_section(-1)),
                          ("Move Down", lambda: self.move_section(1))]:
            FlatButton(side, text, cmd).pack(fill="x", pady=2)
        FlatButton(side, "Delete Section", self.delete_section, "danger").pack(fill="x", pady=2)

        # text area
        right = tk.Frame(body, bg=BG, padx=6, pady=12)
        right.pack(side="left", fill="both", expand=True)
        self.sec_label = tk.Label(right, text="", bg=BG, fg=NEON,
                                  font=("Helvetica", 13, "bold"))
        self.sec_label.pack(anchor="w", padx=(0, 14), pady=(0, 6))
        self.count_var = tk.StringVar()
        tk.Label(right, textvariable=self.count_var, anchor="e", bg=BG, fg=MUTED,
                 font=("Helvetica", 9)).pack(side="bottom", fill="x", padx=(0, 14), pady=(6, 0))
        scroll = make_scrollbar(right, None)
        scroll.pack(side="right", fill="y", padx=(0, 14))
        self.text = tk.Text(right, wrap="word", undo=True, font=("Georgia", 13),
                            bg=SURFACE, fg=TEXT, insertbackground=NEON,
                            selectbackground="#2A6B16", selectforeground=TEXT,
                            relief="flat", bd=0, padx=18, pady=14, spacing3=4,
                            highlightthickness=1, highlightbackground=BORDER,
                            highlightcolor=NEON, yscrollcommand=scroll.set)
        self.text.pack(fill="both", expand=True)
        scroll.config(command=self.text.yview)
        self.text.bind("<KeyRelease>", lambda e: self.update_count())

    def new_article(self):
        title = simpledialog.askstring("New Draft", "Draft title:", parent=self)
        if not title:
            return
        article = {"title": title.strip() or "Untitled",
                   "updated": self.now(),
                   "sections": [{"title": "Introduction", "text": ""}]}
        self.articles.append(article)
        self.save_data()
        self.open_article(article)

    def open_article(self, article):
        self.store_editor()
        self.current = article
        self.title_var.set(article["title"])
        self.refresh_sections()
        self.sec_index = None
        self.select_section(0)
        self.show("editor")
        self.status.set(f"Editing '{article['title']}'")

    def refresh_sections(self):
        self.sec_list.delete(0, "end")
        for s in self.current["sections"]:
            self.sec_list.insert("end", "  " + s["title"])

    def select_section(self, index):
        self.sec_list.selection_clear(0, "end")
        self.sec_list.selection_set(index)
        self.sec_index = index
        section = self.current["sections"][index]
        self.sec_label.config(text=section["title"])
        self.text.delete("1.0", "end")
        self.text.insert("1.0", section["text"])
        self.text.edit_reset()
        self.update_count()

    def on_section_select(self, event):
        sel = self.sec_list.curselection()
        if not sel or self.current is None or sel[0] == self.sec_index:
            return                      # nothing new clicked: keep cursor and undo history
        self.store_editor()
        self.select_section(sel[0])

    def store_editor(self):
        """Copy what is on screen back into the current article."""
        if self.current is None or self.sec_index is None:
            return
        if self.sec_index < len(self.current["sections"]):
            self.current["sections"][self.sec_index]["text"] = self.text.get("1.0", "end-1c")
        self.current["title"] = self.title_var.get().strip() or "Untitled"

    def update_count(self):
        if self.current is None:
            return
        section_words = word_count(self.text.get("1.0", "end-1c"))
        total = sum(word_count(s["text"]) for i, s in enumerate(self.current["sections"])
                    if i != self.sec_index) + section_words
        self.count_var.set(f"Section: {section_words} words   |   Article: {total} words")

    def add_section(self):
        if self.current is None:
            return
        name = simpledialog.askstring("Add Section", "Section title:", parent=self)
        if not name:
            return
        self.store_editor()
        self.current["sections"].append({"title": name.strip(), "text": ""})
        self.refresh_sections()
        self.select_section(len(self.current["sections"]) - 1)

    def rename_section(self):
        if self.current is None or self.sec_index is None:
            return
        section = self.current["sections"][self.sec_index]
        name = simpledialog.askstring("Rename Section", "New title:",
                                      initialvalue=section["title"], parent=self)
        if name:
            self.store_editor()
            section["title"] = name.strip()
            self.refresh_sections()
            self.select_section(self.sec_index)

    def move_section(self, direction):
        if self.current is None or self.sec_index is None:
            return
        self.store_editor()
        i, j = self.sec_index, self.sec_index + direction
        sections = self.current["sections"]
        if 0 <= j < len(sections):
            sections[i], sections[j] = sections[j], sections[i]
            self.refresh_sections()
            self.select_section(j)

    def delete_section(self):
        if self.current is None or self.sec_index is None:
            return
        sections = self.current["sections"]
        if len(sections) == 1:
            messagebox.showinfo("Delete Section", "A draft needs at least one section.")
            return
        if messagebox.askyesno(
                "Delete Section",
                f"Are you sure you want to delete '{sections[self.sec_index]['title']}'?"):
            del sections[self.sec_index]
            self.refresh_sections()
            self.sec_index = None
            self.select_section(0)

    def save_article(self):
        """Save the current work to Drafts."""
        if self.current is None:
            return
        self.store_editor()
        self.current["updated"] = self.now()
        if self.save_data():
            self.status.set(f"Saved to Drafts at {time.strftime('%H:%M:%S')}")

    def archive_current_article(self):
        if self.current:
            self.archive_article(self.current)

    def export_article(self):
        """Write the whole article (title + every section) to a file on this computer."""
        if self.current is None:
            return
        self.store_editor()
        safe_name = "".join(c for c in self.current["title"] if c not in '<>:"/\\|?*').strip()
        path = filedialog.asksaveasfilename(
            defaultextension=".txt", initialfile=(safe_name or "article") + ".txt",
            filetypes=[("Text files", "*.txt")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.current["title"] + "\n" + "=" * len(self.current["title"]) + "\n\n")
                for s in self.current["sections"]:
                    f.write(s["title"] + "\n" + "-" * len(s["title"]) + "\n" + s["text"] + "\n\n")
        except OSError as err:
            messagebox.showerror("Export failed", f"Could not write the file:\n{err}")
            return
        self.status.set(f"Exported to {path}")

    def on_close(self):
        self.store_editor()
        if not self.save_data() and not messagebox.askyesno(
                "Quit anyway?", "Your latest changes could not be saved. Quit anyway?"):
            return
        self.destroy()


if __name__ == "__main__":
    WritingApp().mainloop()