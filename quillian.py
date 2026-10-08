"""
Writr — Tkinter Desktop Edition
--------------------------------
A dark, green-accented writing platform desktop app, styled after the
"Writr" web app mockup: Dashboard / Writing / Drafts / Saves views.

Data is stored locally in a JSON file (writr_data.json, created next to
this script on first run) so everything persists between sessions.

Run with:  python writr_tkinter.py
Requires only the Python standard library (tkinter, json, os).
"""

import json
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from pathlib import Path
from datetime import datetime

# --------------------------------------------------------------------------
# Config / palette
# --------------------------------------------------------------------------

DATA_FILE = Path(__file__).resolve().parent / "writr_data.json"

BG = "#0a0a0a"
PANEL = "#111111"
PANEL2 = "#161616"
BORDER = "#232323"
TEXT = "#f2f2f0"
MUTED = "#7a7a78"
ACCENT = "#39ff6a"
ACCENT_DIM = "#1c4d2c"

FONT_SANS = ("Segoe UI", 10)
FONT_SANS_B = ("Segoe UI", 10, "bold")
FONT_MONO = ("Consolas", 9)
FONT_TITLE = ("Segoe UI", 22, "bold")
FONT_STAT = ("Segoe UI", 24, "bold")
FONT_EDITOR = ("Georgia", 13)


# --------------------------------------------------------------------------
# Persistence
# --------------------------------------------------------------------------

def seed_data():
    return {
        "user_name": "",
        "drafts": [],
        "saves": [],
        "boards": [],
        "streak": [],
    }


def load_data():
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    data = seed_data()
    save_data(data)
    return data


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------

def word_count(text):
    return len(text.split()) if text.strip() else 0


def time_ago(iso_ts):
    try:
        ts = datetime.fromisoformat(iso_ts)
    except (ValueError, TypeError):
        return ""
    diff = datetime.now() - ts
    hours = diff.total_seconds() / 3600
    if hours < 1:
        return "just now"
    if hours < 24:
        h = int(hours)
        return f"{h} hour{'s' if h != 1 else ''} ago"
    days = int(hours // 24)
    return f"{days} day{'s' if days != 1 else ''} ago"


def excerpt_of(text, length=100):
    t = " ".join(text.split())
    return (t[:length] + "…") if len(t) > length else (t or "Empty draft…")


# --------------------------------------------------------------------------
# Main application
# --------------------------------------------------------------------------

class WritrApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Writr")
        self.root.geometry("1150x720")
        self.root.configure(bg=BG)

        self.data = load_data()
        self.current_draft_id = None  # None -> unsaved new draft

        self._build_style()
        self._build_header()
        self._build_views()

        # Keep the most common actions usable from the keyboard as well as
        # from the buttons.  ``bind_all`` also works while the editor has
        # focus (a normal root binding does not).
        self.root.bind_all("<Control-s>", self._on_save_shortcut)
        self.root.bind_all("<Control-n>", self._on_new_shortcut)
        self.root.protocol("WM_DELETE_WINDOW", self._close)

        self.show_view("dashboard")

    def _on_save_shortcut(self, event=None):
        if self.views.get("writing") and self.views["writing"].winfo_ismapped():
            self.save_draft()
        return "break"

    def _on_new_shortcut(self, event=None):
        self.new_draft()
        return "break"

    def _close(self):
        # Do not silently lose text when the window is closed.
        if (self.views.get("writing") and self.views["writing"].winfo_ismapped()
                and self.editor.edit_modified()):
            if messagebox.askyesno("Unsaved changes", "Save this draft before closing?"):
                self.save_draft()
        self.root.destroy()

    # ------------------------------------------------------------------
    # Style
    # ------------------------------------------------------------------

    def _build_style(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("Header.TFrame", background=BG)

        style.configure("TLabel", background=BG, foreground=TEXT, font=FONT_SANS)
        style.configure("Panel.TLabel", background=PANEL, foreground=TEXT, font=FONT_SANS)
        style.configure("Muted.TLabel", background=BG, foreground=MUTED, font=FONT_MONO)
        style.configure("PanelMuted.TLabel", background=PANEL, foreground=MUTED, font=FONT_MONO)

        style.configure("Nav.TButton", background=BG, foreground=MUTED, font=FONT_SANS,
                         borderwidth=0, padding=8)
        style.map("Nav.TButton", foreground=[("active", TEXT)])

        style.configure("NavActive.TButton", background=PANEL, foreground=TEXT,
                         font=FONT_SANS, borderwidth=1, padding=8)

        style.configure("Accent.TButton", background=ACCENT, foreground="#000000",
                         font=FONT_SANS_B, borderwidth=0, padding=8)
        style.map("Accent.TButton", background=[("active", "#5dff8b")])

        style.configure("Ghost.TButton", background=BG, foreground=MUTED,
                         font=FONT_SANS, borderwidth=1, padding=7)
        style.map("Ghost.TButton", foreground=[("active", TEXT)])

    # ------------------------------------------------------------------
    # Header / nav
    # ------------------------------------------------------------------

    def _build_header(self):
        header = tk.Frame(self.root, bg=BG, highlightbackground=BORDER,
                           highlightthickness=0)
        header.pack(fill="x")
        # bottom border
        tk.Frame(header, bg=BORDER, height=1).pack(side="bottom", fill="x")

        inner = tk.Frame(header, bg=BG)
        inner.pack(fill="x", padx=20, pady=10)

        # brand
        brand = tk.Frame(inner, bg=BG)
        brand.pack(side="left")
        logo = tk.Label(brand, text="W", bg=ACCENT, fg="#000000", font=("Segoe UI", 11, "bold"),
                         width=2, height=1)
        logo.pack(side="left")
        tk.Label(brand, text=" WRITR", bg=BG, fg=TEXT, font=("Segoe UI", 12, "bold")).pack(side="left")
        tk.Label(brand, text=" — your words, amplified", bg=BG, fg=MUTED, font=FONT_MONO).pack(side="left")

        # nav buttons
        self.nav_frame = tk.Frame(inner, bg=BG)
        self.nav_frame.pack(side="left", padx=40)
        self.nav_buttons = {}
        for key, label in [("dashboard", "Dashboard"), ("writing", "Writing"),
                            ("drafts", "Drafts"), ("saves", "Saves")]:
            b = tk.Button(self.nav_frame, text=label, bg=BG, fg=MUTED, bd=0,
                          font=FONT_SANS, activebackground=PANEL, activeforeground=TEXT,
                          padx=12, pady=6, command=lambda k=key: self.show_view(k))
            b.pack(side="left", padx=2)
            self.nav_buttons[key] = b

        # right side
        right = tk.Frame(inner, bg=BG)
        right.pack(side="right")
        tk.Label(right, text="L", bg=BG, fg=ACCENT, font=FONT_SANS_B,
                 highlightbackground=BORDER, highlightthickness=1, width=2).pack(side="right", padx=(10, 0))
        tk.Button(right, text="+ New", bg=ACCENT, fg="#000000", bd=0, font=FONT_SANS_B,
                  padx=14, pady=6, command=self.new_draft).pack(side="right")

    def show_view(self, name):
        for key, frame in self.views.items():
            frame.pack_forget()
        self.views[name].pack(fill="both", expand=True)
        for key, btn in self.nav_buttons.items():
            btn.configure(bg=PANEL if key == name else BG, fg=TEXT if key == name else MUTED)
        if name == "dashboard":
            self.refresh_dashboard()
        elif name == "drafts":
            self.refresh_drafts()
        elif name == "saves":
            self.refresh_saves()

    # ------------------------------------------------------------------
    # Build all views (as stacked frames)
    # ------------------------------------------------------------------

    def _build_views(self):
        self.views = {}
        self.views["dashboard"] = self._build_dashboard_view()
        self.views["writing"] = self._build_writing_view()
        self.views["drafts"] = self._build_drafts_view()
        self.views["saves"] = self._build_saves_view()

    # ---------------- Dashboard ----------------

    def _build_dashboard_view(self):
        outer = tk.Frame(self.root, bg=BG)
        canvas = tk.Canvas(outer, bg=BG, highlightthickness=0)
        vbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=BG)
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw", width=1100)
        canvas.configure(yscrollcommand=vbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=20)
        vbar.pack(side="right", fill="y")

        frame = tk.Frame(scroll_frame, bg=BG)
        frame.pack(fill="both", expand=True, pady=24)

        self.welcome_label = tk.Label(frame, bg=BG, fg=TEXT, font=FONT_TITLE, anchor="w")
        self.welcome_label.pack(fill="x")
        tk.Label(frame, text="Your words are waiting. Pick up where you left off.",
                 bg=BG, fg=MUTED, font=FONT_SANS, anchor="w").pack(fill="x", pady=(2, 20))

        # stat cards
        stats_row = tk.Frame(frame, bg=BG)
        stats_row.pack(fill="x", pady=(0, 24))
        self.stat_vars = {}
        for key, label, foot in [
            ("total", "TOTAL WORDS", "across all work"),
            ("active", "ACTIVE DRAFTS", "in progress"),
            ("saved", "SAVED PIECES", "completed"),
            ("week", "THIS WEEK", "words written"),
        ]:
            card = tk.Frame(stats_row, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
            card.pack(side="left", fill="both", expand=True, padx=6, ipadx=12, ipady=10)
            tk.Label(card, text=label, bg=PANEL, fg=MUTED, font=FONT_MONO).pack(anchor="w", padx=6)
            val = tk.Label(card, text="0", bg=PANEL, fg=TEXT, font=FONT_STAT)
            val.pack(anchor="w", padx=6)
            tk.Label(card, text=foot, bg=PANEL, fg=MUTED, font=("Segoe UI", 8)).pack(anchor="w", padx=6, pady=(0, 4))
            self.stat_vars[key] = val

        # two columns: recent drafts / boards
        cols = tk.Frame(frame, bg=BG)
        cols.pack(fill="x", pady=(0, 20))
        left_col = tk.Frame(cols, bg=BG)
        left_col.pack(side="left", fill="both", expand=True, padx=(0, 12))
        right_col = tk.Frame(cols, bg=BG, width=320)
        right_col.pack(side="left", fill="y")

        head = tk.Frame(left_col, bg=BG)
        head.pack(fill="x")
        tk.Label(head, text="RECENT DRAFTS", bg=BG, fg=MUTED, font=FONT_MONO).pack(side="left")
        tk.Button(head, text="view all →", bg=BG, fg=MUTED, bd=0, font=("Segoe UI", 8),
                  command=lambda: self.show_view("drafts")).pack(side="right")
        self.recent_drafts_frame = tk.Frame(left_col, bg=BG)
        self.recent_drafts_frame.pack(fill="x", pady=(8, 0))

        head2 = tk.Frame(right_col, bg=BG)
        head2.pack(fill="x")
        tk.Label(head2, text="WRITING BOARDS", bg=BG, fg=MUTED, font=FONT_MONO).pack(side="left")
        self.boards_frame = tk.Frame(right_col, bg=BG)
        self.boards_frame.pack(fill="x", pady=(8, 4))
        tk.Button(right_col, text="+ new board", bg=BG, fg=MUTED, bd=1, font=("Segoe UI", 9),
                  relief="solid", command=self.add_board).pack(fill="x", pady=(2, 0))

        # streak
        streak_box = tk.Frame(frame, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        streak_box.pack(fill="x", pady=(4, 20), ipady=12, ipadx=12)
        tk.Label(streak_box, text="WRITING STREAK", bg=PANEL, fg=MUTED, font=FONT_MONO).pack(anchor="w", padx=8)
        self.streak_canvas = tk.Canvas(streak_box, bg=PANEL, height=26, highlightthickness=0)
        self.streak_canvas.pack(fill="x", padx=8, pady=6)
        self.streak_foot = tk.Label(streak_box, text="", bg=PANEL, fg=MUTED, font=("Segoe UI", 9))
        self.streak_foot.pack(anchor="w", padx=8)

        return outer

    def refresh_dashboard(self):
        d = self.data
        self.welcome_label.configure(text=f"Welcome back, {d['user_name']}." if d["user_name"]
                         else "Your workspace is ready.")

        total_words = sum(word_count(x["content"]) for x in d["drafts"]) + \
                      sum(x.get("words", 0) for x in d["saves"])
        self.stat_vars["total"].configure(text=f"{total_words:,}")
        self.stat_vars["active"].configure(text=str(len(d["drafts"])))
        self.stat_vars["saved"].configure(text=str(len(d["saves"])))
        week_words = sum(word_count(x["content"]) for x in d["drafts"]
                          if (datetime.now() - datetime.fromisoformat(x["updated"])).days < 7)
        self.stat_vars["week"].configure(text=f"{week_words:,}")

        for w in self.recent_drafts_frame.winfo_children():
            w.destroy()
        recent = sorted(d["drafts"], key=lambda x: x["updated"], reverse=True)[:3]
        if not recent:
            tk.Label(self.recent_drafts_frame, text="No drafts yet.", bg=BG, fg=MUTED,
                      font=FONT_SANS).pack(anchor="w")
        for item in recent:
            self._draft_card(self.recent_drafts_frame, item)

        for w in self.boards_frame.winfo_children():
            w.destroy()
        for b in d["boards"]:
            row = tk.Frame(self.boards_frame, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
            row.pack(fill="x", pady=3, ipady=6, ipadx=6)
            tk.Label(row, text="✎", bg=PANEL, fg=MUTED, font=FONT_SANS,
                     highlightbackground=BORDER, highlightthickness=1, width=2).pack(side="left", padx=(4, 8))
            textcol = tk.Frame(row, bg=PANEL)
            textcol.pack(side="left", fill="x", expand=True)
            tk.Label(textcol, text=b["title"], bg=PANEL, fg=TEXT, font=FONT_SANS_B, anchor="w").pack(fill="x")
            tk.Label(textcol, text=b["when"], bg=PANEL, fg=MUTED, font=("Segoe UI", 8), anchor="w").pack(fill="x")

        self.streak_canvas.delete("all")
        streak = d["streak"]
        n = len(streak)
        self.streak_canvas.update_idletasks()
        width = max(self.streak_canvas.winfo_width(), 800)
        gap = 4
        box_w = (width - gap * (n - 1)) / n
        colors = {0: "#1a1a1a", 1: "#12331e", 2: "#1c4d2c", 3: "#27753f", 4: ACCENT}
        for i, v in enumerate(streak):
            x0 = i * (box_w + gap)
            self.streak_canvas.create_rectangle(x0, 0, x0 + box_w, 20, fill=colors.get(v, "#1a1a1a"),
                                                  outline="")
        streak_days = sum(1 for v in streak if v > 0)
        self.streak_foot.configure(text=f"{streak_days} day streak · keep going")

    def _draft_card(self, parent, item):
        card = tk.Frame(parent, bg=PANEL, highlightbackground=BORDER, highlightthickness=1, cursor="hand2")
        card.pack(fill="x", pady=4, ipady=8, ipadx=10)
        top = tk.Frame(card, bg=PANEL)
        top.pack(fill="x")
        tk.Label(top, text=item["title"], bg=PANEL, fg=TEXT, font=FONT_SANS_B).pack(side="left")
        meta = tk.Label(top, text=f'{word_count(item["content"])}w · {time_ago(item["updated"])}',
                         bg=PANEL, fg=ACCENT, font=FONT_MONO)
        meta.pack(side="right")
        if item["tags"]:
            tags = tk.Frame(card, bg=PANEL)
            tags.pack(fill="x", pady=(4, 0))
            for t in item["tags"]:
                tk.Label(tags, text=f"#{t}", bg=PANEL2, fg=MUTED, font=("Segoe UI", 8)).pack(side="left", padx=2)

        def open_it(event=None, draft_id=item["id"]):
            self.open_draft(draft_id)
        # Labels and tag widgets are children of the card, so binding only
        # the two outer frames made much of the visible card appear inert.
        def bind_card(widget):
            widget.bind("<Button-1>", open_it)
            for child in widget.winfo_children():
                bind_card(child)
        bind_card(card)

    def add_board(self):
        title = simpledialog.askstring("New Board", "Board title:")
        if not title:
            return
        self.data["boards"].insert(0, {"id": f"b{datetime.now().timestamp()}", "title": title, "when": "Today"})
        save_data(self.data)
        self.refresh_dashboard()

    # ---------------- Writing ----------------

    def _build_writing_view(self):
        outer = tk.Frame(self.root, bg=BG)

        sidebar = tk.Frame(outer, bg=BG, width=170, highlightbackground=BORDER, highlightthickness=0)
        sidebar.pack(side="left", fill="y")
        tk.Frame(sidebar, bg=BORDER, width=1).pack(side="right", fill="y")
        tk.Label(sidebar, text="FORMAT", bg=BG, fg=MUTED, font=FONT_MONO).pack(anchor="w", padx=16, pady=(20, 8))
        for label, wrap in [("Bold", "**"), ("Italic", "_"), ("Heading", "## "),
                             ("Quote", "> "), ("List", "- "), ("Link", "[](url)"), ("Code", "`")]:
            tk.Button(sidebar, text=label, bg=BG, fg=MUTED, bd=0, font=FONT_SANS, anchor="w",
                      activebackground=BG, activeforeground=TEXT,
                      command=lambda w=wrap: self.apply_format(w)).pack(fill="x", padx=16, pady=3)

        main = tk.Frame(outer, bg=BG)
        main.pack(side="left", fill="both", expand=True)

        toolbar = tk.Frame(main, bg=BG, highlightbackground=BORDER, highlightthickness=0)
        toolbar.pack(fill="x")
        tk.Frame(toolbar, bg=BORDER, height=1).pack(side="bottom", fill="x")
        tb_inner = tk.Frame(toolbar, bg=BG)
        tb_inner.pack(fill="x", padx=20, pady=12)

        self.title_entry = tk.Entry(tb_inner, bg=BG, fg=TEXT, insertbackground=TEXT, bd=0,
                                      font=("Segoe UI", 13, "bold"))
        self.title_entry.pack(side="left", fill="x")
        self.title_entry.insert(0, "Untitled")

        right = tk.Frame(tb_inner, bg=BG)
        right.pack(side="right")
        self.wordcount_label = tk.Label(right, text="0 words", bg=BG, fg=MUTED, font=FONT_MONO)
        self.wordcount_label.pack(side="left", padx=(0, 14))
        tk.Button(right, text="Mark complete", bg=BG, fg=MUTED, bd=1, relief="solid",
                  font=("Segoe UI", 9), padx=10, pady=5, command=self.complete_draft).pack(side="left", padx=(0, 8))
        tk.Button(right, text="Save", bg=ACCENT, fg="#000000", bd=0, font=FONT_SANS_B,
                  padx=16, pady=5, command=self.save_draft).pack(side="left")

        self.editor = tk.Text(main, bg=BG, fg=TEXT, insertbackground=TEXT, bd=0,
                               font=FONT_EDITOR, wrap="word", undo=True, padx=40, pady=28)
        self.editor.pack(fill="both", expand=True)
        self.editor.bind("<<Modified>>", self._on_editor_modified)

        return outer

    def apply_format(self, wrap):
        """Apply the selected markdown format without losing the selection."""
        try:
            start = self.editor.index("sel.first")
            end = self.editor.index("sel.last")
            sel = self.editor.get(start, end)
        except tk.TclError:
            start = end = self.editor.index("insert")
            sel = ""

        if "url" in wrap:
            insert = f"[{sel or 'text'}](url)"
        elif wrap.endswith(" "):
            # Prefix formats (heading, quote, and list) apply to each
            # selected line, rather than wrapping the entire selection.
            if sel:
                insert = "\n".join(wrap + line for line in sel.split("\n"))
            else:
                insert = wrap
        elif wrap == "**":
            insert = f"**{sel or 'bold text'}**"
        elif wrap == "_":
            insert = f"_{sel or 'italic text'}_"
        elif wrap == "`":
            insert = f"`{sel or 'code'}'".replace("'", "`")
        else:
            insert = wrap + (sel or "text") + wrap

        self.editor.delete(start, end)
        self.editor.insert(start, insert)
        # Keep the newly formatted text selected so another format can be
        # applied immediately, and return focus to the editor after clicking
        # a formatting button.
        self.editor.tag_remove("sel", "1.0", tk.END)
        self.editor.tag_add("sel", start, f"{start} + {len(insert)} chars")
        self.editor.focus_set()
        self._update_wordcount()

    def _on_editor_modified(self, event=None):
        self.editor.edit_modified(False)
        self._update_wordcount()

    def _update_wordcount(self):
        text = self.editor.get("1.0", "end-1c")
        self.wordcount_label.configure(text=f"{word_count(text):,} words")

    def new_draft(self):
        self.current_draft_id = None
        self.title_entry.delete(0, tk.END)
        self.title_entry.insert(0, "Untitled")
        self.editor.delete("1.0", tk.END)
        self._update_wordcount()
        self.show_view("writing")

    def open_draft(self, draft_id):
        item = next((x for x in self.data["drafts"] if x["id"] == draft_id), None)
        if not item:
            return
        self.current_draft_id = draft_id
        self.title_entry.delete(0, tk.END)
        self.title_entry.insert(0, item["title"])
        self.editor.delete("1.0", tk.END)
        self.editor.insert("1.0", item["content"])
        self._update_wordcount()
        self.show_view("writing")

    def save_draft(self):
        title = self.title_entry.get().strip() or "Untitled"
        content = self.editor.get("1.0", "end-1c")
        if self.current_draft_id:
            item = next((x for x in self.data["drafts"] if x["id"] == self.current_draft_id), None)
            if item:
                item["title"] = title
                item["content"] = content
                item["updated"] = datetime.now().isoformat()
        else:
            new_id = f"d{datetime.now().timestamp()}"
            self.data["drafts"].insert(0, {
                "id": new_id, "title": title, "content": content,
                "tags": [], "updated": datetime.now().isoformat(),
            })
            self.current_draft_id = new_id
        save_data(self.data)
        self._flash_saved()

    def _flash_saved(self):
        self.root.title("Writr — saved ✓")
        self.root.after(1200, lambda: self.root.title("Writr"))

    def complete_draft(self):
        title = self.title_entry.get().strip() or "Untitled"
        content = self.editor.get("1.0", "end-1c")
        self.data["saves"].insert(0, {
            "id": f"s{datetime.now().timestamp()}",
            "title": title,
            "excerpt": excerpt_of(content),
            "tags": [],
            "words": word_count(content),
            "date": datetime.now().strftime("%b %d, %Y"),
        })
        if self.current_draft_id:
            self.data["drafts"] = [x for x in self.data["drafts"] if x["id"] != self.current_draft_id]
        self.current_draft_id = None
        save_data(self.data)
        self.show_view("saves")

    # ---------------- Drafts list ----------------

    def _build_drafts_view(self):
        outer = tk.Frame(self.root, bg=BG)
        frame = tk.Frame(outer, bg=BG)
        frame.pack(fill="both", expand=True, padx=24, pady=24)

        tk.Label(frame, text="Drafts", bg=BG, fg=TEXT, font=FONT_TITLE, anchor="w").pack(fill="x")
        self.drafts_count_label = tk.Label(frame, text="", bg=BG, fg=MUTED, font=FONT_SANS, anchor="w")
        self.drafts_count_label.pack(fill="x", pady=(2, 14))

        self.draft_search_var = tk.StringVar()
        self.draft_search_var.trace_add("write", lambda *a: self.refresh_drafts())
        search = tk.Entry(frame, textvariable=self.draft_search_var, bg=PANEL, fg=TEXT,
                           insertbackground=TEXT, bd=1, relief="solid", font=FONT_SANS)
        search.pack(fill="x", pady=(0, 16), ipady=5)
        self._placeholder(search, "Search drafts...")

        canvas = tk.Canvas(frame, bg=BG, highlightthickness=0)
        vbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        self.drafts_list_frame = tk.Frame(canvas, bg=BG)
        self.drafts_list_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.drafts_list_frame, anchor="nw", width=1050)
        canvas.configure(yscrollcommand=vbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        vbar.pack(side="right", fill="y")

        return outer

    def _placeholder(self, entry, text):
        entry.insert(0, text)
        entry.configure(fg=MUTED)
        def on_focus_in(e):
            if entry.get() == text:
                entry.delete(0, tk.END)
                entry.configure(fg=TEXT)
        def on_focus_out(e):
            if not entry.get():
                entry.insert(0, text)
                entry.configure(fg=MUTED)
        entry.bind("<FocusIn>", on_focus_in)
        entry.bind("<FocusOut>", on_focus_out)

    def refresh_drafts(self):
        q = self.draft_search_var.get().lower()
        if q == "search drafts...":
            q = ""
        drafts = sorted(self.data["drafts"], key=lambda x: x["updated"], reverse=True)
        drafts = [d for d in drafts if q in d["title"].lower()]

        self.drafts_count_label.configure(text=f"{len(self.data['drafts'])} pieces in progress")

        for w in self.drafts_list_frame.winfo_children():
            w.destroy()
        if not drafts:
            tk.Label(self.drafts_list_frame, text="No drafts match your search.",
                      bg=BG, fg=MUTED, font=FONT_SANS).pack(anchor="w")
        for item in drafts:
            row = tk.Frame(self.drafts_list_frame, bg=PANEL, highlightbackground=BORDER,
                            highlightthickness=1, cursor="hand2")
            row.pack(fill="x", pady=5, ipady=10, ipadx=12)

            top = tk.Frame(row, bg=PANEL)
            top.pack(fill="x")
            tk.Label(top, text=item["title"], bg=PANEL, fg=TEXT, font=("Segoe UI", 12, "bold")).pack(side="left")
            tk.Button(top, text="delete", bg=PANEL, fg=MUTED, bd=1, relief="solid",
                      font=("Segoe UI", 8), command=lambda i=item["id"]: self.delete_draft(i)).pack(side="right")

            tk.Label(row, text=excerpt_of(item["content"]), bg=PANEL, fg=MUTED, font=("Segoe UI", 9),
                     anchor="w", wraplength=850, justify="left").pack(fill="x", pady=4)

            bottom = tk.Frame(row, bg=PANEL)
            bottom.pack(fill="x")
            tagbox = tk.Frame(bottom, bg=PANEL)
            tagbox.pack(side="left")
            for t in item["tags"]:
                tk.Label(tagbox, text=f"#{t}", bg=PANEL2, fg=MUTED, font=("Segoe UI", 8)).pack(side="left", padx=2)
            tk.Label(bottom, text=f'{word_count(item["content"])} words · {time_ago(item["updated"])}',
                     bg=PANEL, fg=ACCENT, font=FONT_MONO).pack(side="right")

            def open_it(event=None, draft_id=item["id"]):
                self.open_draft(draft_id)
            def bind_row(widget):
                # Keep the delete button's own command intact.
                if widget is not delete_button:
                    widget.bind("<Button-1>", open_it)
                for child in widget.winfo_children():
                    bind_row(child)

            delete_button = top.winfo_children()[-1]
            bind_row(row)

    def delete_draft(self, draft_id):
        if not messagebox.askyesno("Delete Draft", "Permanently delete this draft?"):
            return
        self.data["drafts"] = [d for d in self.data["drafts"] if d["id"] != draft_id]
        save_data(self.data)
        self.refresh_drafts()

    # ---------------- Saves list ----------------

    def _build_saves_view(self):
        outer = tk.Frame(self.root, bg=BG)
        frame = tk.Frame(outer, bg=BG)
        frame.pack(fill="both", expand=True, padx=24, pady=24)

        tk.Label(frame, text="Saves", bg=BG, fg=TEXT, font=FONT_TITLE, anchor="w").pack(fill="x")
        self.saves_count_label = tk.Label(frame, text="", bg=BG, fg=MUTED, font=FONT_SANS, anchor="w")
        self.saves_count_label.pack(fill="x", pady=(2, 16))

        canvas = tk.Canvas(frame, bg=BG, highlightthickness=0)
        vbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        self.saves_list_frame = tk.Frame(canvas, bg=BG)
        self.saves_list_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.saves_list_frame, anchor="nw", width=1050)
        canvas.configure(yscrollcommand=vbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        vbar.pack(side="right", fill="y")

        return outer

    def refresh_saves(self):
        saves = self.data["saves"]
        total_words = sum(s.get("words", 0) for s in saves)
        self.saves_count_label.configure(text=f"{len(saves)} completed · {total_words:,} words total")

        for w in self.saves_list_frame.winfo_children():
            w.destroy()
        if not saves:
            tk.Label(self.saves_list_frame, text="Nothing saved yet.", bg=BG, fg=MUTED,
                      font=FONT_SANS).pack(anchor="w")
        for item in saves:
            row = tk.Frame(self.saves_list_frame, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
            row.pack(fill="x", pady=5, ipady=10, ipadx=12)

            top = tk.Frame(row, bg=PANEL)
            top.pack(fill="x")
            tk.Label(top, text=item["title"], bg=PANEL, fg=TEXT, font=("Segoe UI", 12, "bold")).pack(side="left")
            tk.Label(top, text="saved", bg=ACCENT_DIM, fg=ACCENT, font=FONT_MONO, padx=6).pack(side="right")

            tk.Label(row, text=item["excerpt"], bg=PANEL, fg=MUTED, font=("Segoe UI", 9),
                     anchor="w", wraplength=850, justify="left").pack(fill="x", pady=4)

            bottom = tk.Frame(row, bg=PANEL)
            bottom.pack(fill="x")
            tagbox = tk.Frame(bottom, bg=PANEL)
            tagbox.pack(side="left")
            for t in item["tags"]:
                tk.Label(tagbox, text=f"#{t}", bg=PANEL2, fg=MUTED, font=("Segoe UI", 8)).pack(side="left", padx=2)
            tk.Label(bottom, text=f'{item.get("words", 0):,} words · {item.get("date", "")}',
                     bg=PANEL, fg=ACCENT, font=FONT_MONO).pack(side="right")


if __name__ == "__main__":
    root = tk.Tk()
    app = WritrApp(root)
    root.mainloop()