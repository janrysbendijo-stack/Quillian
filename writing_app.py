import json
import re
import html
import calendar
import os
import time
import tkinter as tk
from datetime import date, timedelta
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
        self.section_text_snapshot = None
        self.pending_writing_articles = set()

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
        self.bind_all("<Control-s>", self.shortcut_save)
        self.bind_all("<Control-n>", self.shortcut_new)
        self.bind_all("<Control-f>", self.shortcut_find)
        self.bind_all("<Control-h>", self.shortcut_replace)
        self.bind_all("<Control-b>", lambda e: self.format_shortcut("bold"))
        self.bind_all("<Control-i>", lambda e: self.format_shortcut("italic"))
        self.bind_all("<Control-u>", lambda e: self.format_shortcut("underline"))
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
            for article in data:
                if (not isinstance(article, dict)
                    or not isinstance(article.get("title"), str)
                    or not isinstance(article.get("updated"), str)
                    or not isinstance(article.get("sections"), list)
                    or not article["sections"]
                    or not isinstance(article.get("archived", False), bool)):
                    raise ValueError("Invalid article format")
                for section in article["sections"]:
                    if (not isinstance(section, dict)
                        or not isinstance(section.get("title"), str)
                        or not isinstance(section.get("text"), str)):
                        raise ValueError("Invalid section format")
            return data
        except (ValueError, OSError, TypeError):
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
        pending_ids = set(self.pending_writing_articles)
        today = date.today().isoformat()
        for article in self.articles:
            if id(article) not in pending_ids:
                continue
            activity = article.get("writing_activity")
            if not isinstance(activity, list):
                activity = []
            if today not in activity:
                activity.append(today)
            article["writing_activity"] = activity
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
        self.pending_writing_articles.difference_update(pending_ids)
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
        self.dash_frame = tk.Frame(self.content, bg=BG)
        self.dash_scroll = make_scrollbar(self.dash_frame, None)
        self.dash_canvas = tk.Canvas(self.dash_frame, bg=BG, highlightthickness=0,
                                     yscrollcommand=self.dash_scroll.set)
        self.dash_scroll.config(command=self.dash_canvas.yview)
        self.dash_scroll.pack(side="right", fill="y")
        self.dash_canvas.pack(side="left", fill="both", expand=True)
        self.dashboard_content = tk.Frame(self.dash_canvas, bg=BG, padx=28, pady=24)
        self.dash_content_window = self.dash_canvas.create_window(
            (0, 0), window=self.dashboard_content, anchor="nw")
        self.dashboard_content.bind(
            "<Configure>",
            lambda e: self.dash_canvas.configure(scrollregion=self.dash_canvas.bbox("all")))
        self.dash_canvas.bind(
            "<Configure>",
            lambda e: self.dash_canvas.itemconfigure(self.dash_content_window, width=e.width))
        self.bind_all("<MouseWheel>", self.scroll_dashboard, add="+")
        page_header(self.dashboard_content, "Dashboard",
                    "Double-click a draft to keep writing.")

        self.stat_vars = {k: tk.StringVar() for k in ("drafts", "archived", "words")}
        stats = tk.Frame(self.dashboard_content, bg=BG)
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

        tk.Label(self.dashboard_content, text="RECENTLY EDITED", bg=BG, fg=MUTED,
                 font=("Helvetica", 9, "bold")).pack(anchor="w", pady=(0, 8))
        self.recent_hint = tk.Label(self.dashboard_content, bg=BG, fg=MUTED, anchor="w")
        self.recent_hint.pack(fill="x")
        self.recent_list = make_list(self.dashboard_content)
        self.recent_list.config(height=8)
        self.recent_list.pack(fill="x")
        self.recent_list.bind("<Double-Button-1>",
                              lambda e: on_item(self.recent_list, e) and self.open_recent())

        productivity = tk.Frame(self.dashboard_content, bg=BG)
        productivity.pack(fill="x", pady=(18, 0))
        productivity_header = tk.Frame(productivity, bg=BG)
        productivity_header.pack(fill="x", pady=(0, 8))
        tk.Label(productivity_header, text="PRODUCTIVITY LOG", bg=BG, fg=MUTED,
                 font=("Helvetica", 9, "bold")).pack(side="left")
        self.streak_var = tk.StringVar()
        tk.Label(productivity_header, textvariable=self.streak_var, bg=BG, fg=NEON,
                 font=("Helvetica", 10, "bold")).pack(side="right")

        month_row = tk.Frame(productivity, bg=BG)
        month_row.pack(fill="x", pady=(0, 6))
        FlatButton(month_row, "<", lambda: self.change_log_month(-1),
                   padx=10, pady=3).pack(side="left")
        self.log_month_var = tk.StringVar()
        tk.Label(month_row, textvariable=self.log_month_var, bg=BG, fg=TEXT,
                 font=("Helvetica", 11, "bold")).pack(side="left", expand=True)
        self.month_activity_var = tk.StringVar()
        tk.Label(month_row, textvariable=self.month_activity_var, bg=BG, fg=MUTED,
                 font=("Helvetica", 9)).pack(side="left", padx=8)
        FlatButton(month_row, ">", lambda: self.change_log_month(1),
                   padx=10, pady=3).pack(side="right")

        self.log_month = date.today().replace(day=1)
        calendar_grid = tk.Frame(productivity, bg=BG)
        calendar_grid.pack(fill="x")
        self.log_day_cells = []
        for column, weekday in enumerate(("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")):
            calendar_grid.grid_columnconfigure(column, weight=1, uniform="calendar-day")
            tk.Label(calendar_grid, text=weekday, bg=BG, fg=MUTED,
                     font=("Helvetica", 8, "bold")).grid(
                         row=0, column=column, sticky="ew", pady=(0, 3))
        for row in range(1, 7):
            cells = []
            for column in range(7):
                cell = tk.Label(calendar_grid, text="", bg=PANEL, fg=MUTED,
                                font=("Helvetica", 9), height=1,
                                highlightthickness=1, highlightbackground=BORDER)
                cell.grid(row=row, column=column, sticky="ew", padx=2, pady=2)
                cells.append(cell)
            self.log_day_cells.append(cells)

    def scroll_dashboard(self, event):
        if self.dash_frame.winfo_ismapped():
            self.dash_canvas.yview_scroll(int(-event.delta / 120), "units")
            return "break"

    def recent_articles(self):
        return sorted(self.active_articles(), key=lambda a: a["updated"], reverse=True)[:8]

    def writing_dates(self):
        dates = set()
        for article in self.articles:
            activity = article.get("writing_activity", [])
            if not isinstance(activity, list):
                continue
            for value in activity:
                if not isinstance(value, str):
                    continue
                try:
                    dates.add(date.fromisoformat(value))
                except ValueError:
                    continue
        return dates

    def current_writing_streak(self, writing_dates):
        day = date.today()
        if day not in writing_dates:
            day -= timedelta(days=1)
        streak = 0
        while day in writing_dates:
            streak += 1
            day -= timedelta(days=1)
        return streak

    def change_log_month(self, offset):
        month_index = self.log_month.year * 12 + self.log_month.month - 1 + offset
        year, month = divmod(month_index, 12)
        self.log_month = date(year, month + 1, 1)
        self.refresh_productivity_log()

    def refresh_productivity_log(self):
        writing_dates = self.writing_dates()
        streak = self.current_writing_streak(writing_dates)
        self.streak_var.set(f"{streak} day streak")

        year, month = self.log_month.year, self.log_month.month
        self.log_month_var.set(self.log_month.strftime("%B %Y"))
        monthly_dates = {day for day in writing_dates
                         if day.year == year and day.month == month}
        self.month_activity_var.set(f"{len(monthly_dates)} writing days")
        weeks = calendar.Calendar(firstweekday=0).monthdayscalendar(year, month)
        weeks.extend([[0] * 7 for _ in range(6 - len(weeks))])
        today = date.today()
        for row, week in enumerate(weeks):
            for column, day_number in enumerate(week):
                cell = self.log_day_cells[row][column]
                if not day_number:
                    cell.config(text="", bg=BG, highlightbackground=BG)
                    continue
                day = date(year, month, day_number)
                active = day in writing_dates
                cell.config(text=str(day_number),
                            bg="#173014" if active else PANEL,
                            fg=NEON if active else TEXT,
                            font=("Helvetica", 9, "bold" if active else "normal"),
                            highlightbackground=NEON if day == today else BORDER)

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
        self.refresh_productivity_log()

    def open_recent(self):
        sel = self.recent_list.curselection()
        if sel:
            self.open_article(self.recent_articles()[sel[0]])

    # ---------- drafts ----------
    def build_drafts(self):
        self.drafts_frame = tk.Frame(self.content, bg=BG, padx=28, pady=24)
        page_header(self.drafts_frame, "Drafts",
                    "Double-click a draft, or select it and press Editor.")

        search_row = tk.Frame(self.drafts_frame, bg=BG)
        search_row.pack(fill="x", pady=(0, 10))
        tk.Label(search_row, text="SEARCH", bg=BG, fg=MUTED).pack(side="left", padx=(0, 10))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.refresh_drafts())
        tk.Entry(search_row, textvariable=self.search_var, bg=SURFACE, fg=TEXT,
                 insertbackground=NEON, relief="flat", font=("Helvetica", 11),
                 highlightthickness=1, highlightbackground=BORDER,
                 highlightcolor=NEON).pack(side="left", fill="x", expand=True, ipady=5)
        tk.Label(search_row, text="SORT", bg=BG, fg=MUTED).pack(side="left", padx=(12, 6))
        self.sort_var = tk.StringVar(value="Newest")
        sort_menu = tk.OptionMenu(search_row, self.sort_var, "Newest", "Oldest", "Title A-Z", "Title Z-A")
        sort_menu.config(bg=PANEL, fg=TEXT, activebackground=BORDER, activeforeground=NEON,
                         highlightthickness=0, relief="flat", width=11)
        sort_menu["menu"].config(bg=PANEL, fg=TEXT, activebackground=NEON, activeforeground=BG)
        sort_menu.pack(side="left")
        self.sort_var.trace_add("write", lambda *_: self.refresh_drafts())
        self.visible_drafts = []
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
        query = self.search_var.get().strip().casefold()
        self.visible_drafts = [a for a in self.active_articles()
                               if query in a["title"].casefold()]
        mode = self.sort_var.get()
        if mode == "Newest":
            self.visible_drafts.sort(key=lambda a: a.get("updated", ""), reverse=True)
        elif mode == "Oldest":
            self.visible_drafts.sort(key=lambda a: a.get("updated", ""))
        elif mode == "Title A-Z":
            self.visible_drafts.sort(key=lambda a: a["title"].casefold())
        elif mode == "Title Z-A":
            self.visible_drafts.sort(key=lambda a: a["title"].casefold(), reverse=True)
        for a in self.visible_drafts:
            self.drafts_list.insert(
                "end", f"  {a['title']}   -   {self.article_words(a)} words   -   {a['updated']}")
        self.drafts_hint.config(
            text=("No matching drafts." if query else "No drafts yet. Press New to start writing.")
            if not self.visible_drafts else "")

    def selected_draft(self):
        sel = self.drafts_list.curselection()
        if not sel:
            messagebox.showinfo("Select", "Select a draft first.")
            return None
        if sel[0] >= len(self.visible_drafts):
            return None
        return self.visible_drafts[sel[0]]

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
        if self.save_data():
            self.status.set(f"'{article['title']}' moved to the archive.")
            self.show("archive")

    def restore_selected_article(self):
        a = self.selected_archived()
        if not a:
            return
        a["archived"] = False
        a["updated"] = self.now()
        if self.save_data():
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
        if self.save_data():
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
        FlatButton(top, "Find / Replace", self.open_find_replace).pack(side="left", padx=3)
        tk.Frame(self.editor_frame, bg=NEON, height=1).pack(fill="x")
        toolbar = tk.Frame(self.editor_frame, bg=SURFACE, padx=12, pady=5)
        toolbar.pack(fill="x")
        for name, kind in [("Bold", "bold"), ("Italic", "italic"), ("Underline", "underline"),
                           ("Left", "left"), ("Center", "center"), ("Right", "right")]:
            FlatButton(toolbar, name, lambda k=kind: self.apply_format(k)).pack(side="left", padx=3)
        FlatButton(toolbar, "Grammar Check", self.check_grammar, "primary").pack(side="right", padx=3)
        FlatButton(toolbar, "Export HTML", self.export_html).pack(side="right", padx=3)

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
        self.text.tag_configure("bold", font=("Georgia", 13, "bold"))
        self.text.tag_configure("italic", font=("Georgia", 13, "italic"))
        self.text.tag_configure("underline", underline=True)
        self.text.tag_configure("center", justify="center")
        self.text.tag_configure("right", justify="right")
        self.text.tag_configure("grammar_issue", underline=True, foreground="#FFB86B")
        self.text.pack(fill="both", expand=True)
        scroll.config(command=self.text.yview)
        self.text.bind("<<Modified>>", self.on_text_modified)

    def on_text_modified(self, event=None):
        if self.text.edit_modified():
            self.update_count()
            self.text.edit_modified(False)

    def format_shortcut(self, kind):
        if self.current is not None and self.focus_get() == self.text:
            self.apply_format(kind)
        return "break"

    def apply_format(self, kind):
        if self.current is None:
            return
        if kind in ("left", "center", "right"):
            try:
                start = self.text.index("sel.first linestart")
                end = self.text.index("sel.last lineend")
            except tk.TclError:
                start = self.text.index("insert linestart")
                end = self.text.index("insert lineend")
            end = self.text.index(f"{end}+1c")
            for tag in ("center", "right"):
                self.text.tag_remove(tag, start, end)
            if kind != "left":
                self.text.tag_add(kind, start, end)
        else:
            try:
                start, end = self.text.index("sel.first"), self.text.index("sel.last")
            except tk.TclError:
                self.status.set("Select text before applying Bold, Italic, or Underline.")
                return
            if self.text.tag_nextrange(kind, start, end):
                self.text.tag_remove(kind, start, end)
            else:
                self.text.tag_add(kind, start, end)
        self.status.set("Formatting updated. Save to keep changes.")

    def check_grammar(self):
        """Offline writing hints, not a comprehensive grammar or spelling engine."""
        if self.current is None:
            return
        content = self.text.get("1.0", "end-1c")
        self.text.tag_remove("grammar_issue", "1.0", "end")
        findings = []
        patterns = [
            (r"\b([A-Za-z]+)\s+\1\b", "Repeated word", re.I),
            (r" {2,}", "Extra spaces", 0),
            (r"\s+([,.!?;:])", "Space before punctuation", 0),
            (r"\b[aA]\s+(?=[aeiouAEIOU][A-Za-z])", "Consider 'an' before a vowel sound", 0),
            (r"\b[aA]n\s+(?=[bcdfgjklmnpqrstvwxyzBCDFGJKLMNPQRSTVWXYZ][A-Za-z])", "Check the article 'an'", 0),
        ]
        for pattern, message, flags in patterns:
            for match in re.finditer(pattern, content, flags):
                findings.append((match.start(), match.end(), message))
        for match in re.finditer(r"(?:^|[.!?]\s+)([a-z])", content):
            findings.append((match.start(1), match.end(1), "Sentence may need a capital letter"))
        for a, b, message in findings:
            self.text.tag_add("grammar_issue", f"1.0+{a}c", f"1.0+{b}c")
        if findings:
            examples = "\n".join(f"• {message}: {content[a:b]!r}" for a, b, message in findings[:12])
            messagebox.showinfo("Grammar Assistant", f"Found {len(findings)} possible issue(s) in this section.\n\n{examples}\n\nOrange text marks suggestions. Review manually; suggestions may be incorrect.")
        else:
            messagebox.showinfo("Grammar Assistant", "No basic writing issues detected. This does not guarantee correct grammar or spelling.")

    def export_html(self):
        if self.current is None:
            return
        self.store_editor()
        path = filedialog.asksaveasfilename(defaultextension=".html", filetypes=[("HTML documents", "*.html")])
        if not path:
            return
        parts = ["<!DOCTYPE html><html><head><meta charset='utf-8'><title>",
                 html.escape(self.current["title"]),
                 "</title></head><body style='font-family:Georgia,serif;max-width:850px;margin:40px auto;line-height:1.6'>",
                 "<h1>", html.escape(self.current["title"]), "</h1>"]
        for section in self.current["sections"]:
            parts.extend(["<h2>", html.escape(section["title"]), "</h2>"])
            raw = section["text"]
            fmt = section.get("formatting", {})
            # Character-wise styling preserves overlapping bold/italic/underline ranges.
            runs = []
            for i, char in enumerate(raw):
                active = []
                for tag in ("bold", "italic", "underline", "center", "right"):
                    if any(isinstance(r, list) and len(r) == 2 and r[0] <= i < r[1]
                           for r in fmt.get(tag, [])):
                        active.append(tag)
                runs.append((char, tuple(active)))
            lines = []
            for line in "".join(x[0] for x in runs).split("\n"):
                lines.append(line)
            offset = 0
            for line in lines:
                styles = []
                for j, char in enumerate(line):
                    active = runs[offset+j][1] if offset+j < len(runs) else ()
                    css = []
                    if "bold" in active: css.append("font-weight:bold")
                    if "italic" in active: css.append("font-style:italic")
                    if "underline" in active: css.append("text-decoration:underline")
                    escaped = html.escape(char)
                    styles.append(f'<span style="{ ";".join(css) }">{escaped}</span>' if css else escaped)
                alignment = "right" if any("right" in runs[k][1] for k in range(offset, min(offset+len(line), len(runs)))) else ("center" if any("center" in runs[k][1] for k in range(offset, min(offset+len(line), len(runs)))) else "left")
                parts.extend([f'<div style="text-align:{alignment};min-height:1.4em">', "".join(styles), "</div>"])
                offset += len(line) + 1
        parts.append("</body></html>")
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("".join(parts))
        except OSError as err:
            messagebox.showerror("Export failed", str(err))
            return
        self.status.set(f"Formatted HTML exported: {path}")

    def new_article(self):
        title = simpledialog.askstring("New Draft", "Draft title:", parent=self)
        if not title:
            return
        article = {"title": title.strip() or "Untitled",
                   "updated": self.now(),
                   "sections": [{"title": "Introduction", "text": ""}]}
        self.articles.append(article)
        if self.save_data():
            self.open_article(article)
        else:
            self.articles.remove(article)

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
        self.section_text_snapshot = section["text"]
        for tag, ranges in section.get("formatting", {}).items():
            if tag not in ("bold", "italic", "underline", "center", "right") or not isinstance(ranges, list):
                continue
            for pair in ranges:
                if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                    continue
                try:
                    a, b = int(pair[0]), int(pair[1])
                    if 0 <= a < b <= len(section["text"]):
                        self.text.tag_add(tag, f"1.0+{a}c", f"1.0+{b}c")
                except (ValueError, TypeError, tk.TclError):
                    continue
        self.text.edit_modified(False)
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
            section = self.current["sections"][self.sec_index]
            text = self.text.get("1.0", "end-1c")
            if text != self.section_text_snapshot and text.strip():
                self.pending_writing_articles.add(id(self.current))
            section["text"] = text
            self.section_text_snapshot = text
            formatting = {}
            for tag in ("bold", "italic", "underline", "center", "right"):
                positions = self.text.tag_ranges(tag)
                if positions:
                    formatting[tag] = [[len(self.text.get("1.0", str(positions[i]))),
                                        len(self.text.get("1.0", str(positions[i+1])))]
                                       for i in range(0, len(positions), 2)]
            section["formatting"] = formatting
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
            self.store_editor()
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

    # ---------- shortcuts and find/replace ----------
    def shortcut_save(self, event=None):
        if self.current is not None:
            self.save_article()
        return "break"

    def shortcut_new(self, event=None):
        self.new_article()
        return "break"

    def shortcut_find(self, event=None):
        if self.current is not None:
            self.open_find_replace()
            self.find_entry.focus_set()
        return "break"

    def shortcut_replace(self, event=None):
        if self.current is not None:
            self.open_find_replace()
            self.replace_entry.focus_set()
        return "break"

    def open_find_replace(self):
        if self.current is None:
            return
        if hasattr(self, "find_window") and self.find_window.winfo_exists():
            self.find_window.lift()
            return
        win = tk.Toplevel(self)
        self.find_window = win
        win.title("Find and Replace - Current Section")
        win.geometry("460x230")
        win.resizable(False, False)
        win.configure(bg=BG)
        win.transient(self)
        self.find_var = tk.StringVar()
        self.replace_var = tk.StringVar()
        for label, variable in (("Find", self.find_var), ("Replace with", self.replace_var)):
            row = tk.Frame(win, bg=BG)
            row.pack(fill="x", padx=16, pady=(12, 0))
            tk.Label(row, text=label, bg=BG, fg=TEXT, width=13, anchor="w").pack(side="left")
            entry = tk.Entry(row, textvariable=variable, bg=SURFACE, fg=TEXT,
                             insertbackground=NEON, relief="flat", font=("Helvetica", 11))
            entry.pack(side="left", fill="x", expand=True, ipady=5)
            if label == "Find":
                self.find_entry = entry
            else:
                self.replace_entry = entry
        self.find_info = tk.StringVar(value="Searches the currently open section (case-insensitive).")
        tk.Label(win, textvariable=self.find_info, bg=BG, fg=MUTED,
                 wraplength=430).pack(padx=16, pady=12)
        buttons = tk.Frame(win, bg=BG)
        buttons.pack(padx=16, fill="x")
        FlatButton(buttons, "Find Next", self.find_next, "primary").pack(side="left", padx=(0, 6))
        FlatButton(buttons, "Replace", self.replace_one).pack(side="left", padx=(0, 6))
        FlatButton(buttons, "Replace All", self.replace_all).pack(side="left")
        self.find_entry.focus_set()
        self.find_entry.bind("<Return>", lambda e: self.find_next())

    def find_next(self):
        term = self.find_var.get()
        if not term:
            self.find_info.set("Enter a word or phrase to find.")
            return
        start = self.text.index("insert")
        idx = self.text.search(term, start, stopindex="end", nocase=True)
        if not idx:
            idx = self.text.search(term, "1.0", stopindex="end", nocase=True)
        if not idx:
            self.find_info.set("No matches in this section.")
            return
        end = self.text.index(f"{idx}+{len(term)}c")
        self.text.tag_remove("sel", "1.0", "end")
        self.text.tag_add("sel", idx, end)
        self.text.mark_set("insert", end)
        self.text.see(idx)
        self.text.focus_set()
        self.find_info.set("Match found.")

    def replace_one(self):
        term = self.find_var.get()
        if not term:
            self.find_info.set("Enter a word or phrase to replace.")
            return
        selected = self.text.tag_ranges("sel")
        if selected and self.text.get(selected[0], selected[1]).casefold() == term.casefold():
            start, end = str(selected[0]), str(selected[1])
        else:
            self.find_next()
            selected = self.text.tag_ranges("sel")
            if not selected or self.text.get(selected[0], selected[1]).casefold() != term.casefold():
                return
            start, end = str(selected[0]), str(selected[1])
        self.text.delete(start, end)
        self.text.insert(start, self.replace_var.get())
        self.text.mark_set("insert", f"{start}+{len(self.replace_var.get())}c")
        self.update_count()
        self.find_info.set("Replaced one match.")

    def replace_all(self):
        term = self.find_var.get()
        if not term:
            self.find_info.set("Enter a word or phrase to replace.")
            return
        count = 0
        cursor = "1.0"
        while True:
            idx = self.text.search(term, cursor, stopindex="end", nocase=True)
            if not idx:
                break
            end = self.text.index(f"{idx}+{len(term)}c")
            self.text.delete(idx, end)
            replacement = self.replace_var.get()
            self.text.insert(idx, replacement)
            cursor = self.text.index(f"{idx}+{len(replacement)}c")
            count += 1
        self.update_count()
        self.find_info.set(f"Replaced {count} match(es) in this section.")

    def on_close(self):
        self.store_editor()
        if not self.save_data() and not messagebox.askyesno(
                "Quit anyway?", "Your latest changes could not be saved. Quit anyway?"):
            return
        self.destroy()


if __name__ == "__main__":
    WritingApp().mainloop()