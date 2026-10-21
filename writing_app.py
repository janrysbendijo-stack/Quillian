import json
import copy
import shutil
import re
import html
import os
import time
import calendar
from datetime import date, timedelta
import tkinter as tk
from tkinter import messagebox, simpledialog, filedialog, ttk

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "articles.json")
ACTIVITY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "productivity_log.json")

# ---------- theme ----------
THEMES = {
    "dark": {
        "BG": "#0B0B0B", "NAVBG": "#080808", "SURFACE": "#141414",
        "PANEL": "#1C1C1C", "BORDER": "#303030", "NEON": "#39FF14",
        "NEON_HOVER": "#6BFF4F", "TEXT": "#EDEDED", "MUTED": "#8A8A8A",
        "DANGER": "#FF5C5C", "ODD": "#202020", "SELECTED": "#235B1A",
        "HEAT1": "#173016", "HEAT2": "#22551A", "HEAT3": "#2E7A20",
        "MENU_HOVER": "#292929", "DANGER_HOVER": "#2A1414",
        "TEXT_SELECTION": "#2A6B16", "GRAMMAR_ISSUE": "#FFB86B",
    },
    "light": {
        "BG": "#F5F7F2", "NAVBG": "#E8ECE4", "SURFACE": "#FFFFFF",
        "PANEL": "#EDF1E9", "BORDER": "#CCD4C6", "NEON": "#238516",
        "NEON_HOVER": "#1A6F10", "TEXT": "#20251E", "MUTED": "#657060",
        "DANGER": "#C93636", "ODD": "#F0F3ED", "SELECTED": "#CFE8C9",
        "HEAT1": "#E0F0DC", "HEAT2": "#B8DFAF", "HEAT3": "#78BF68",
        "MENU_HOVER": "#DCE4D7", "DANGER_HOVER": "#F8E4E4",
        "TEXT_SELECTION": "#CFE8C9", "GRAMMAR_ISSUE": "#A65B00",
    },
}
THEME_NAME = "dark"


def set_theme_colors(name):
    global THEME_NAME, BG, NAVBG, SURFACE, PANEL, BORDER, NEON, NEON_HOVER
    global TEXT, MUTED, DANGER, ODD, SELECTED, HEAT1, HEAT2, HEAT3
    global MENU_HOVER, DANGER_HOVER, TEXT_SELECTION, GRAMMAR_ISSUE, KINDS
    THEME_NAME = name
    globals().update(THEMES[name])
    KINDS = {
        "primary": (NEON, SURFACE, NEON_HOVER, SURFACE),
        "secondary": (PANEL, TEXT, BORDER, NEON),
        "danger": (PANEL, DANGER, DANGER_HOVER, DANGER),
        "nav": (NAVBG, MUTED, SURFACE, NEON),
    }


set_theme_colors(THEME_NAME)


class FlatButton(tk.Label):
    """A flat button with a hover effect (a Label, so colors work on every OS)."""

    def __init__(self, parent, text, command, kind="secondary", **kw):
        self.kind = kind
        self.command = command
        self.active = False
        options = dict(font=("Helvetica", 10, "bold"), padx=15, pady=9, cursor="hand2")
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


def display_date(value):
    """Show stored YYYY-MM-DD HH:MM timestamps in a readable local format."""
    try:
        return time.strftime("%b %d, %Y  •  %I:%M %p",
                             time.strptime(value, "%Y-%m-%d %H:%M"))
    except (ValueError, TypeError, OverflowError):
        return str(value)


def make_document_table(parent, show_sections=False, show_goal=False):
    """Consistent numbered document tables, with section count on Dashboard."""
    style = ttk.Style(parent)
    style.theme_use("clam")
    style.configure("Quillian.Treeview", background=SURFACE, fieldbackground=SURFACE,
                    foreground=TEXT, borderwidth=0, relief="flat", rowheight=43,
                    font=("Helvetica", 10))
    style.configure("Quillian.Treeview.Heading", background=PANEL, foreground=MUTED,
                    relief="flat", font=("Helvetica", 9, "bold"), padding=(12, 13))
    style.map("Quillian.Treeview", background=[("selected", SELECTED)],
              foreground=[("selected", TEXT)])
    columns = ["number", "title"]
    if show_sections: columns.append("sections")
    columns.append("words")
    if show_goal: columns.append("goal")
    columns.append("modified")
    table = ttk.Treeview(parent, columns=columns, show="headings",
                         selectmode="browse", style="Quillian.Treeview")
    # WORDS and LAST MODIFIED are both centered so the number no longer
    # sits right next to (and looks merged with) the date.
    config = {
        "number": ("NO.", 65, False, "center"),
        "title": ("TITLE", 280, True, "w"),
        "sections": ("SECTIONS", 110, False, "center"),
        "words": ("WORDS", 110, False, "center"),
        "goal": ("WORD GOAL", 125, False, "center"),
        "modified": ("LAST MODIFIED", 250, False, "center"),
    }
    for col in columns:
        heading, width, stretch, anchor = config[col]
        table.heading(col, text=heading, anchor=anchor)
        table.column(col, width=width, minwidth=55, stretch=stretch, anchor=anchor)
    table.configure(takefocus=True)
    for col in columns:
        table.heading(col, command=lambda c=col: table_sort(table, c))
    return table


def add_table_scrollbar(table, parent):
    bar = make_scrollbar(parent, table.yview)
    bar.pack(side="right", fill="y")
    table.configure(yscrollcommand=bar.set)
    return bar


def set_zebra(table):
    table.tag_configure("even", background=SURFACE)
    table.tag_configure("odd", background=ODD)


def table_sort(table, key, reverse=False):
    entries = [(table.set(iid, key), iid) for iid in table.get_children("")]
    if key in ("number", "sections", "words"):
        entries.sort(key=lambda item: int(item[0] or 0), reverse=reverse)
    elif key == "goal":
        entries.sort(key=lambda item: int(item[0].split("/")[0]) if "/" in item[0] else 0, reverse=reverse)
    elif key == "modified":
        def parsed(item):
            try: return time.strptime(item[0], "%b %d, %Y  •  %I:%M %p")
            except ValueError: return time.strptime("Jan 01, 1970  •  12:00 AM", "%b %d, %Y  •  %I:%M %p")
        entries.sort(key=parsed, reverse=reverse)
    else:
        entries.sort(key=lambda item: item[0].casefold(), reverse=reverse)
    for index, (_, iid) in enumerate(entries):
        table.move(iid, "", index)
        table.item(iid, tags=("even" if index % 2 == 0 else "odd",))
    for column in table["columns"]:
        table.heading(column, command=lambda c=column: table_sort(table, c, c == key and not reverse))


def table_selected_index(table):
    selected = table.selection()
    return int(selected[0]) if selected else None


def page_header(parent, title, subtitle=""):
    tk.Label(parent, text=title, bg=BG, fg=TEXT,
             font=("Helvetica", 24, "bold")).pack(anchor="w")
    tk.Frame(parent, bg=NEON, height=3, width=48).pack(anchor="w", pady=(6, 6))
    if subtitle:
        tk.Label(parent, text=subtitle, bg=BG, fg=MUTED).pack(anchor="w", pady=(0, 8))


def word_count(text):
    return len(text.split())


def activity_words_by_day(events):
    words_by_day = {}
    for event in events:
        try:
            activity_day = date.fromisoformat(str(event["timestamp"])[:10])
            words = int(event.get("delta", event.get("words", 0)))
        except (KeyError, TypeError, ValueError):
            continue
        if words > 0:
            words_by_day[activity_day] = words_by_day.get(activity_day, 0) + words
    return words_by_day


def writing_streaks(words_by_day, today):
    active_days = {day for day, words in words_by_day.items()
                   if words > 0 and day <= today}
    current_day = today if today in active_days else today - timedelta(days=1)
    current = 0
    while current_day in active_days:
        current += 1
        current_day -= timedelta(days=1)

    best = 0
    streak = 0
    previous_day = None
    for active_day in sorted(active_days):
        streak = streak + 1 if previous_day == active_day - timedelta(days=1) else 1
        best = max(best, streak)
        previous_day = active_day
    return current, best, active_days


def on_item(listbox, event):
    """True only if the click landed on a real row (not on the blank space below)."""
    box = listbox.bbox(listbox.nearest(event.y))
    return bool(box) and box[1] <= event.y <= box[1] + box[3]


AUTOSAVE_MS = 30000     # autosave every 30 seconds


class WritingApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Quillian")
        self.geometry("1000x760")
        self.minsize(800, 680)
        self.configure(bg=BG)
        self.theme_name = THEME_NAME

        self.startup_warning = None
        self.articles = self.load_data()
        self.activity_log = self.load_activity_log()
        self.activity_word_baseline = {}
        for event in self.activity_log:
            if "article_id" in event and "words" in event:
                self.activity_word_baseline[event["article_id"]] = int(event["words"])
        self.last_saved = self.serialize()   # what is currently on disk
        self.current = None        # the article being edited
        for article in self.articles:
            self.ensure_article_id(article)
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

    def load_activity_log(self):
        if not os.path.exists(ACTIVITY_FILE):
            return []
        try:
            with open(ACTIVITY_FILE, "r", encoding="utf-8") as f:
                events = json.load(f)
            if not isinstance(events, list):
                return []
            return [e for e in events if isinstance(e, dict) and
                    all(k in e for k in ("timestamp", "title", "action", "words"))][-300:]
        except (OSError, ValueError, TypeError):
            self.activity_warning = "Productivity log could not be read; existing log was left unchanged."
            return []

    def ensure_article_id(self, article):
        if not article.get("id"):
            import uuid
            article["id"] = uuid.uuid4().hex
        return article["id"]

    def record_activity(self, action, article=None):
        """Record activity and net word change since last logged state."""
        article = article or self.current
        if article is None or getattr(self, "activity_warning", None):
            return
        article_id = self.ensure_article_id(article)
        words = self.article_words(article)
        baseline = self.activity_word_baseline.get(article_id)
        delta = words - baseline if baseline is not None else (words if action in ("Create", "Import") else 0)
        event = {"timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                 "article_id": article_id, "title": article["title"],
                 "action": action, "words": words, "delta": delta}
        updated = (self.activity_log + [event])[-300:]
        tmp = ACTIVITY_FILE + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(updated, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, ACTIVITY_FILE)
            self.activity_log = updated
            self.activity_word_baseline[article_id] = words
        except OSError:
            self.status.set("Draft saved, but productivity activity could not be logged.")

    def unique_title(self, proposed, exclude=None):
        proposed = proposed.strip() or "Untitled"
        return not any(a is not exclude and a["title"].casefold() == proposed.casefold()
                       for a in self.articles)

    def validate_editor_title(self):
        if self.current is None: return True
        title = self.title_var.get().strip() or "Untitled"
        if not self.unique_title(title, self.current):
            messagebox.showwarning("Duplicate Title", "Another draft already uses this title. Choose a different title.")
            self.title_var.set(self.current["title"])
            return False
        return True

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
                        self.record_activity("Autosave")
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

        self.theme_button = FlatButton(
            nav, "Light mode", self.toggle_theme, "secondary",
            anchor="w", padx=24, pady=10)
        self.theme_button.pack(side="bottom", fill="x", padx=8, pady=16)

        self.content = tk.Frame(self, bg=BG)
        self.content.pack(side="right", fill="both", expand=True)

    def toggle_theme(self):
        old_colors = THEMES[self.theme_name]
        new_name = "light" if self.theme_name == "dark" else "dark"
        new_colors = THEMES[new_name]
        color_map = {old_colors[key]: new_colors[key] for key in old_colors}
        self.theme_name = new_name
        set_theme_colors(new_name)

        color_options = (
            "bg", "background", "fg", "foreground", "activebackground",
            "activeforeground", "disabledforeground", "highlightbackground",
            "highlightcolor", "insertbackground", "selectbackground",
            "selectforeground", "troughcolor",
        )

        def recolor(widget):
            for option in color_options:
                try:
                    value = widget.cget(option)
                    if isinstance(value, str) and value in color_map:
                        widget.configure(**{option: color_map[value]})
                except tk.TclError:
                    continue
            if isinstance(widget, FlatButton):
                widget.paint(False)
            for child in widget.winfo_children():
                recolor(child)

        recolor(self)
        self.apply_editor_theme()
        self.theme_button.config(text="Dark mode" if new_name == "light" else "Light mode")
        style = ttk.Style(self)
        style.configure("Quillian.Treeview", background=SURFACE,
                        fieldbackground=SURFACE, foreground=TEXT)
        style.configure("Quillian.Treeview.Heading", background=PANEL,
                        foreground=MUTED)
        style.map("Quillian.Treeview", background=[("selected", SELECTED)],
                  foreground=[("selected", TEXT)])
        style.configure("Quillian.Horizontal.TProgressbar", troughcolor=BORDER,
                        background=NEON, bordercolor=BORDER, lightcolor=NEON,
                        darkcolor=NEON)
        for table in (self.recent_list, self.drafts_list, self.archive_list):
            table.tag_configure("even", background=SURFACE)
            table.tag_configure("odd", background=ODD)
        self.refresh_dashboard()
        self.refresh_drafts()
        self.refresh_archive()

    def apply_editor_theme(self):
        for frame, color in (
                (self.editor_frame, BG), (self.editor_body, BG),
                (self.editor_side, BG), (self.editor_right, BG),
                (self.editor_top, SURFACE), (self.editor_toolbar, SURFACE),
                (self.editor_recovery_bar, SURFACE)):
            frame.configure(bg=color)

        for label, bg, fg in (
                (self.editor_title_label, SURFACE, MUTED),
                (self.editor_goal_label, SURFACE, MUTED),
                (self.editor_progress_label, SURFACE, NEON),
                (self.editor_section_label, BG, MUTED),
                (self.editor_count_label, BG, MUTED),
                (self.sec_label, BG, NEON)):
            label.configure(bg=bg, fg=fg)

        for entry in (self.title_entry, self.goal_entry):
            entry.configure(bg=BG, fg=TEXT, insertbackground=NEON,
                            highlightbackground=BORDER, highlightcolor=NEON)

        self.sec_list.configure(
            bg=SURFACE, fg=TEXT, selectbackground=NEON, selectforeground=BG,
            highlightbackground=BORDER, highlightcolor=NEON)
        self.editor_scrollbar.configure(
            bg=BORDER, troughcolor=SURFACE, activebackground=NEON)
        self.text.configure(
            bg=SURFACE, fg=TEXT, insertbackground=NEON,
            selectbackground=TEXT_SELECTION, selectforeground=TEXT,
            highlightbackground=BORDER, highlightcolor=NEON)
        self.text.tag_configure("grammar_issue", foreground=GRAMMAR_ISSUE)

    def show(self, name):
        if name != "editor":
            if self.current is not None and not self.validate_editor_title():
                return
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
        if name != "editor":
            self.status.set({"dashboard": "Dashboard ready.", "drafts": "Drafts ready.", "archive": "Archive ready."}[name])

        highlight = name if name in self.nav_buttons else "drafts"   # editor belongs to Drafts
        for key, btn in self.nav_buttons.items():
            btn.set_active(key == highlight)

    # ---------- dashboard ----------
    def build_dashboard(self):
        self.dash_frame = tk.Frame(self.content, bg=BG, padx=28, pady=14)
        page_header(self.dash_frame, "Dashboard", "Double-click a draft to keep writing.")

        self.stat_vars = {k: tk.StringVar() for k in ("drafts", "archived", "words")}
        stats = tk.Frame(self.dash_frame, bg=BG)
        stats.pack(fill="x", pady=(6, 12))
        for i, (key, label) in enumerate([("drafts", "DRAFTS"),
                                          ("archived", "ARCHIVED"),
                                          ("words", "TOTAL WORDS")]):
            stats.grid_columnconfigure(i, weight=1, uniform="stat")
            box = tk.Frame(stats, bg=SURFACE, highlightthickness=1,
                           highlightbackground=BORDER, padx=18, pady=10)
            box.grid(row=0, column=i, sticky="ew", padx=(0, 12 if i < 2 else 0))
            tk.Label(box, textvariable=self.stat_vars[key], bg=SURFACE, fg=NEON,
                     font=("Helvetica", 28, "bold")).pack(anchor="w")
            tk.Label(box, text=label, bg=SURFACE, fg=MUTED,
                     font=("Helvetica", 9, "bold")).pack(anchor="w")
            if key in ("drafts", "archived"):
                target = "drafts" if key == "drafts" else "archive"
                for widget in (box, *box.winfo_children()):
                    widget.configure(cursor="hand2")
                    widget.bind("<Button-1>", lambda e, n=target: self.show(n))

        tk.Label(self.dash_frame, text="RECENTLY EDITED", bg=BG, fg=MUTED,
                 font=("Helvetica", 9, "bold")).pack(anchor="w", pady=(0, 8))
        self.recent_hint = tk.Label(self.dash_frame, bg=BG, fg=MUTED, anchor="w")
        self.recent_hint.pack(fill="x")
        recent_area = tk.Frame(self.dash_frame, bg=BG)
        recent_area.pack(fill="both", expand=True, pady=(8, 0))
        self.recent_list = make_document_table(recent_area, show_sections=True)
        add_table_scrollbar(self.recent_list, recent_area)
        self.recent_list.pack(side="left", fill="both", expand=True)
        set_zebra(self.recent_list)
        self.recent_list.bind("<Double-Button-1>", lambda e: self.open_recent())
        # Keep the recent drafts compact so the calendar remains visible.
        recent_area.pack_configure(expand=False)
        self.recent_list.configure(height=3)
        log_heading = tk.Frame(self.dash_frame, bg=BG)
        log_heading.pack(fill="x", pady=(10, 5))
        tk.Label(log_heading, text="PRODUCTIVITY LOG", bg=BG, fg=MUTED,
                 font=("Helvetica", 9, "bold")).pack(side="left")
        self.log_summary = tk.StringVar(value="CURRENT STREAK 0 DAYS  ·  BEST 0 DAYS")
        tk.Label(log_heading, textvariable=self.log_summary, bg=BG, fg=NEON,
                 font=("Helvetica", 9, "bold")).pack(side="right")

        calendar_area = tk.Frame(self.dash_frame, bg=BG)
        calendar_area.pack(fill="x")
        month_bar = tk.Frame(calendar_area, bg=BG)
        month_bar.pack(fill="x", pady=(0, 5))
        self.productivity_month = date.today().replace(day=1)
        FlatButton(month_bar, "‹", lambda: self.shift_productivity_month(-1),
                   padx=9, pady=2, font=("Helvetica", 12, "bold")).pack(side="left")
        self.productivity_month_label = tk.Label(
            month_bar, bg=BG, fg=TEXT, font=("Helvetica", 10, "bold"))
        self.productivity_month_label.pack(side="left", expand=True)
        FlatButton(month_bar, "›", lambda: self.shift_productivity_month(1),
                   padx=9, pady=2, font=("Helvetica", 12, "bold")).pack(side="right")
        self.productivity_grid = tk.Frame(calendar_area, bg=BG)
        self.productivity_grid.pack(fill="x")
        for column, weekday in enumerate(("M", "T", "W", "T", "F", "S", "S")):
            self.productivity_grid.grid_columnconfigure(column, weight=1, uniform="day")
            tk.Label(self.productivity_grid, text=weekday, bg=BG, fg=MUTED,
                     font=("Helvetica", 8, "bold")).grid(
                         row=0, column=column, sticky="ew", padx=2, pady=(0, 2))
        calendar_footer = tk.Frame(calendar_area, bg=BG)
        calendar_footer.pack(fill="x", pady=(5, 0))
        self.productivity_footer = tk.StringVar()
        tk.Label(calendar_footer, textvariable=self.productivity_footer,
                 bg=BG, fg=MUTED, font=("Helvetica", 9)).pack(side="left")
        legend = tk.Frame(calendar_footer, bg=BG)
        legend.pack(side="right")
        tk.Label(legend, text="LESS", bg=BG, fg=MUTED,
                 font=("Helvetica", 8)).pack(side="left", padx=(0, 3))
        for color in (SURFACE, HEAT1, HEAT2, HEAT3, NEON):
            tk.Label(legend, text=" ", bg=color, width=1).pack(side="left", padx=1)
        tk.Label(legend, text="MORE", bg=BG, fg=MUTED,
                 font=("Helvetica", 8)).pack(side="left", padx=(3, 0))

    def recent_articles(self):
        return sorted(self.active_articles(), key=lambda a: a["updated"], reverse=True)[:8]

    def shift_productivity_month(self, amount):
        month_index = self.productivity_month.year * 12 + self.productivity_month.month - 1 + amount
        year, month = divmod(month_index, 12)
        candidate = date(year, month + 1, 1)
        if candidate <= date.today().replace(day=1):
            self.productivity_month = candidate
            self.refresh_productivity_calendar()

    def refresh_productivity_calendar(self):
        today = date.today()
        words_by_day = activity_words_by_day(self.activity_log)
        current_streak, best_streak, active_days = writing_streaks(words_by_day, today)
        self.log_summary.set(
            f"CURRENT STREAK {current_streak} DAYS  ·  BEST {best_streak} DAYS")
        month = self.productivity_month
        self.productivity_month_label.config(text=f"{calendar.month_name[month.month]} {month.year}")
        for widget in self.productivity_grid.grid_slaves():
            if int(widget.grid_info()["row"]) > 0:
                widget.destroy()

        month_weeks = calendar.monthcalendar(month.year, month.month)
        for row, week in enumerate(month_weeks, start=1):
            for column, day_number in enumerate(week):
                if not day_number:
                    continue
                activity_day = date(month.year, month.month, day_number)
                words = words_by_day.get(activity_day, 0)
                if words >= 100:
                    cell_bg = NEON
                    cell_fg = BG
                elif words >= 50:
                    cell_bg = HEAT3
                    cell_fg = TEXT
                elif words >= 20:
                    cell_bg = HEAT2
                    cell_fg = TEXT
                elif words:
                    cell_bg = HEAT1
                    cell_fg = TEXT
                else:
                    cell_bg = SURFACE
                    cell_fg = MUTED
                tk.Label(
                    self.productivity_grid, text=str(day_number), bg=cell_bg, fg=cell_fg,
                    font=("Helvetica", 9, "bold" if words else "normal"),
                    height=1, padx=2, pady=1,
                    highlightthickness=1 if activity_day == today else 0,
                    highlightbackground=NEON).grid(
                        row=row, column=column, sticky="ew", padx=2, pady=1)

        month_days = [day for day in active_days
                      if day.year == month.year and day.month == month.month]
        month_words = sum(words_by_day[day] for day in month_days)
        self.productivity_footer.set(
            f"{month_words:,} words written  ·  {len(month_days)} active days")

    def refresh_dashboard(self):
        active = self.active_articles()
        self.stat_vars["drafts"].set(len(active))
        self.stat_vars["archived"].set(len(self.archived_articles()))
        self.stat_vars["words"].set(sum(self.article_words(a) for a in active))

        self.recent_list.delete(*self.recent_list.get_children())
        for i, a in enumerate(self.recent_articles()):
            self.recent_list.insert("", "end", iid=str(i),
                                    values=(f"{i + 1:02d}", a["title"], len(a["sections"]),
                                             self.article_words(a), display_date(a["updated"])),
                                     tags=("even" if i % 2 == 0 else "odd",))
        self.recent_hint.config(
            text="" if active else "No drafts yet. Open Drafts and press New to start writing.")
        self.refresh_productivity_calendar()

    def open_recent(self):
        idx = table_selected_index(self.recent_list)
        if idx is not None:
            self.open_article(self.recent_articles()[idx])

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
        self.drafts_count_var = tk.StringVar(value="Total Drafts: 0  |  Showing: 0 of 0")
        tk.Label(self.drafts_frame, textvariable=self.drafts_count_var,
                 bg=BG, fg=NEON, anchor="w", font=("Helvetica", 10, "bold")).pack(fill="x", pady=(0, 5))
        self.drafts_hint = tk.Label(self.drafts_frame, bg=BG, fg=MUTED, anchor="w")
        self.drafts_hint.pack(fill="x")
        draft_area = tk.Frame(self.drafts_frame, bg=BG)
        draft_area.pack(fill="both", expand=True, pady=(12, 10))
        self.drafts_list = make_document_table(draft_area, show_sections=True, show_goal=True)
        self.drafts_list.configure(height=6)
        add_table_scrollbar(self.drafts_list, draft_area)
        self.drafts_list.pack(side="left", fill="both", expand=True)
        set_zebra(self.drafts_list)
        self.drafts_list.bind("<Button-3>", self.draft_context_menu)
        self.drafts_list.bind("<Button-2>", self.draft_context_menu)
        self.drafts_list.bind("<Double-Button-1>", lambda e: self.open_selected_draft())
        self.draft_menu = tk.Menu(self, tearoff=False, bg=PANEL, fg=TEXT,
                                  activebackground=NEON, activeforeground=BG)
        self.draft_menu.add_command(label="Open", command=self.open_selected_draft)
        self.draft_menu.add_command(label="Archive", command=self.archive_selected_article)
        self.draft_menu.add_separator()
        self.draft_menu.add_command(label="Delete", command=self.delete_selected_draft)

        self.draft_actions = tk.Frame(self.drafts_frame, bg=BG)
        self.draft_actions.pack(anchor="w", pady=(0, 6))
        for text, cmd, kind in [("New", self.new_article, "primary"),
                                ("Import TXT", self.import_txt, "secondary"),
                                ("Editor", self.open_selected_draft, "secondary"),
                                ("Archive", self.archive_selected_article, "secondary"),
                                ("Delete", self.delete_selected_draft, "danger")]:
            FlatButton(self.draft_actions, text, cmd, kind).pack(side="left", padx=(0, 8))

    def draft_context_menu(self, event):
        row = self.drafts_list.identify_row(event.y)
        if not row: return
        self.drafts_list.selection_set(row)
        self.draft_menu.tk_popup(event.x_root, event.y_root)
        self.draft_menu.grab_release()

    def refresh_drafts(self):
        self.drafts_list.delete(*self.drafts_list.get_children())
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
        total_drafts = len(self.active_articles())
        shown_drafts = len(self.visible_drafts)
        self.drafts_count_var.set(
            f"Total Drafts: {total_drafts}  |  Showing: {shown_drafts} of {total_drafts}")
        for i, a in enumerate(self.visible_drafts):
            self.drafts_list.insert("", "end", iid=str(i),
                                    values=(f"{i + 1:02d}", a["title"], len(a["sections"]),
                                             self.article_words(a),
                                              f"{self.article_words(a)}/{a.get('word_goal', 500)}",
                                              display_date(a["updated"])),
                                     tags=("even" if i % 2 == 0 else "odd",))
        self.drafts_hint.config(
            text=("No matching drafts." if query else "No drafts yet. Press New to start writing.")
            if not self.visible_drafts else "")

    def selected_draft(self):
        idx = table_selected_index(self.drafts_list)
        if idx is None:
            messagebox.showinfo("Select", "Select a draft first.")
            return None
        if idx >= len(self.visible_drafts):
            return None
        return self.visible_drafts[idx]

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

        self.archive_count_var = tk.StringVar(value="Total Archived: 0")
        tk.Label(self.archive_frame, textvariable=self.archive_count_var,
                 bg=BG, fg=NEON, anchor="w", font=("Helvetica", 10, "bold")).pack(fill="x", pady=(0, 5))
        self.archive_hint = tk.Label(self.archive_frame, bg=BG, fg=MUTED, anchor="w")
        self.archive_hint.pack(fill="x")
        archive_area = tk.Frame(self.archive_frame, bg=BG)
        archive_area.pack(fill="both", expand=True, pady=(12, 18))
        self.archive_list = make_document_table(archive_area, show_sections=True)
        add_table_scrollbar(self.archive_list, archive_area)
        self.archive_list.pack(side="left", fill="both", expand=True)
        set_zebra(self.archive_list)

        row = tk.Frame(self.archive_frame, bg=BG)
        row.pack(anchor="w")
        FlatButton(row, "Restore", self.restore_selected_article, "primary").pack(
            side="left", padx=(0, 8))
        FlatButton(row, "Delete", self.delete_selected_archived, "danger").pack(side="left")

    def refresh_archive(self):
        self.archive_list.delete(*self.archive_list.get_children())
        archived = self.archived_articles()
        self.archive_count_var.set(f"Total Archived: {len(archived)}")
        for i, a in enumerate(archived):
            self.archive_list.insert("", "end", iid=str(i),
                                     values=(f"{i + 1:02d}", a["title"], len(a["sections"]),
                                             self.article_words(a), display_date(a["updated"])),
                                      tags=("even" if i % 2 == 0 else "odd",))
        self.archive_hint.config(
            text="" if archived else "The archive is empty.")

    def selected_archived(self):
        idx = table_selected_index(self.archive_list)
        if idx is None:
            messagebox.showinfo("Select", "Select an archived draft first.")
            return None
        archived = self.archived_articles()
        return archived[idx] if idx < len(archived) else None

    def archive_article(self, article):
        self.store_editor()
        article["archived"] = True
        article["updated"] = self.now()
        if article is self.current:         # an archived draft can't stay open
            self.current = None
            self.sec_index = None
        if self.save_data():
            self.record_activity("Archive", article)
            self.status.set(f"'{article['title']}' moved to the archive.")
            self.show("archive")

    def restore_selected_article(self):
        a = self.selected_archived()
        if not a:
            return
        a["archived"] = False
        a["updated"] = self.now()
        if self.save_data():
            self.record_activity("Restore", a)
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
        self.editor_top = tk.Frame(self.editor_frame, bg=SURFACE, padx=18, pady=13)
        self.editor_top.pack(fill="x")
        self.editor_title_label = tk.Label(
            self.editor_top, text="TITLE", bg=SURFACE, fg=MUTED,
            font=("Helvetica", 9, "bold"))
        self.editor_title_label.pack(side="left")
        self.title_var = tk.StringVar()
        self.title_entry = tk.Entry(
            self.editor_top, textvariable=self.title_var, font=("Helvetica", 14, "bold"),
            bg=BG, fg=TEXT, insertbackground=NEON, relief="flat",
            highlightthickness=1, highlightbackground=BORDER, highlightcolor=NEON)
        self.title_entry.pack(side="left", fill="x", expand=True, padx=10, ipady=5)
        FlatButton(self.editor_top, "Save", self.save_article, "primary").pack(side="left", padx=3)
        FlatButton(self.editor_top, "Archive", self.archive_current_article).pack(side="left", padx=3)
        FlatButton(self.editor_top, "Export .txt", self.export_article).pack(side="left", padx=3)
        FlatButton(self.editor_top, "Find / Replace", self.open_find_replace).pack(side="left", padx=3)
        tk.Frame(self.editor_frame, bg=NEON, height=1).pack(fill="x")
        self.editor_toolbar = tk.Frame(self.editor_frame, bg=SURFACE, padx=18, pady=11)
        self.editor_toolbar.pack(fill="x")
        for name, kind in [("Bold", "bold"), ("Italic", "italic"), ("Underline", "underline"),
                           ("Left", "left"), ("Center", "center"), ("Right", "right")]:
            FlatButton(self.editor_toolbar, name, lambda k=kind: self.apply_format(k)).pack(side="left", padx=3)
        FlatButton(self.editor_toolbar, "Grammar Check", self.check_grammar, "primary").pack(side="right", padx=3)
        FlatButton(self.editor_toolbar, "Export HTML", self.export_html).pack(side="right", padx=3)

        self.editor_recovery_bar = tk.Frame(self.editor_frame, bg=SURFACE, padx=18, pady=12)
        self.editor_recovery_bar.pack(fill="x")
        self.editor_goal_label = tk.Label(
            self.editor_recovery_bar, text="WORD GOAL", bg=SURFACE, fg=MUTED)
        self.editor_goal_label.pack(side="left", padx=(0, 6))
        self.goal_var = tk.StringVar(value="500")
        self.goal_entry = tk.Entry(
            self.editor_recovery_bar, textvariable=self.goal_var, width=9, bg=BG, fg=TEXT,
            insertbackground=NEON, relief="flat", font=("Helvetica", 11),
            highlightthickness=1, highlightbackground=BORDER)
        self.goal_entry.pack(side="left", padx=(0, 10), ipady=5)
        FlatButton(self.editor_recovery_bar, "Set Goal", self.set_word_goal).pack(side="left", padx=3)
        self.progress_var = tk.StringVar(value="Goal: —")
        self.editor_progress_label = tk.Label(
            self.editor_recovery_bar, textvariable=self.progress_var, bg=SURFACE, fg=NEON,
            font=("Helvetica", 10, "bold"))
        self.editor_progress_label.pack(side="left", padx=12)
        self.goal_bar = ttk.Progressbar(self.editor_recovery_bar, maximum=100, length=165,
                                         mode="determinate", style="Quillian.Horizontal.TProgressbar")
        ttk.Style(self).configure("Quillian.Horizontal.TProgressbar", troughcolor=BORDER,
                                   background=NEON, bordercolor=BORDER, lightcolor=NEON,
                                   darkcolor=NEON, thickness=10)
        self.goal_bar.pack(side="left", padx=(12, 16))
        FlatButton(self.editor_recovery_bar, "History", self.open_history).pack(side="right", padx=3)
        FlatButton(self.editor_recovery_bar, "Backup", self.backup_now).pack(side="right", padx=3)

        self.editor_body = tk.Frame(self.editor_frame, bg=BG)
        self.editor_body.pack(fill="both", expand=True)

        # side panel: sections
        self.editor_side = tk.Frame(self.editor_body, bg=BG, padx=18, pady=16)
        self.editor_side.pack(side="left", fill="y")
        self.editor_section_label = tk.Label(
            self.editor_side, text="SECTIONS", bg=BG, fg=MUTED,
            font=("Helvetica", 9, "bold"))
        self.editor_section_label.pack(anchor="w", pady=(0, 6))
        self.sec_list = make_list(self.editor_side, width=24)
        self.sec_list.pack(fill="y", expand=True, pady=(0, 8))
        self.sec_list.bind("<<ListboxSelect>>", self.on_section_select)
        for text, cmd in [("Add Section", self.add_section),
                          ("Rename", self.rename_section),
                          ("Move Up", lambda: self.move_section(-1)),
                          ("Move Down", lambda: self.move_section(1))]:
            FlatButton(self.editor_side, text, cmd).pack(fill="x", pady=3)
        FlatButton(self.editor_side, "Delete Section", self.delete_section, "danger").pack(fill="x", pady=3)

        # text area
        self.editor_right = tk.Frame(self.editor_body, bg=BG, padx=8, pady=16)
        self.editor_right.pack(side="left", fill="both", expand=True)
        self.sec_label = tk.Label(self.editor_right, text="", bg=BG, fg=NEON,
                                  font=("Helvetica", 13, "bold"))
        self.sec_label.pack(anchor="w", padx=(0, 14), pady=(0, 6))
        self.count_var = tk.StringVar()
        self.editor_count_label = tk.Label(
            self.editor_right, textvariable=self.count_var, anchor="e", bg=BG, fg=MUTED,
            font=("Helvetica", 9))
        self.editor_count_label.pack(side="bottom", fill="x", padx=(0, 14), pady=(6, 0))
        self.editor_scrollbar = make_scrollbar(self.editor_right, None)
        self.editor_scrollbar.pack(side="right", fill="y", padx=(0, 14))
        self.text = tk.Text(self.editor_right, wrap="word", undo=True, font=("Georgia", 13),
                            bg=SURFACE, fg=TEXT, insertbackground=NEON,
                            selectbackground=TEXT_SELECTION, selectforeground=TEXT,
                            relief="flat", bd=0, padx=24, pady=20, spacing3=5,
                            highlightthickness=1, highlightbackground=BORDER,
                            highlightcolor=NEON, yscrollcommand=self.editor_scrollbar.set)
        self.text.tag_configure("bold", font=("Georgia", 13, "bold"))
        self.text.tag_configure("italic", font=("Georgia", 13, "italic"))
        self.text.tag_configure("underline", underline=True)
        self.text.tag_configure("center", justify="center")
        self.text.tag_configure("right", justify="right")
        self.text.tag_configure("grammar_issue", underline=True, foreground=GRAMMAR_ISSUE)
        self.text.pack(fill="both", expand=True)
        self.editor_scrollbar.config(command=self.text.yview)
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
        if not title: return
        if not self.unique_title(title):
            messagebox.showwarning("Duplicate Title", "Another draft already uses this title.")
            return
        article = {"title": title.strip() or "Untitled",
                   "updated": self.now(),
                   "sections": [{"title": "Introduction", "text": ""}]}
        self.articles.append(article)
        if self.save_data():
            self.record_activity("Create", article)
            self.open_article(article)
        else:
            self.articles.remove(article)

    def open_article(self, article):
        self.store_editor()
        self.current = article
        self.title_var.set(article["title"])
        self.goal_var.set(str(article.get("word_goal", 500)))
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
            section["text"] = self.text.get("1.0", "end-1c")
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
        goal = self.current.get("word_goal", 500)
        if not isinstance(goal, int) or goal < 1:
            goal = 500
        self.progress_var.set(f"{total}/{goal} words ({min(100, int(total / goal * 100))}%)")
        self.goal_bar["value"] = min(100, total / max(1, goal) * 100)

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
        if not self.validate_editor_title(): return
        self.store_editor()
        self.record_history()
        self.current["updated"] = self.now()
        if self.save_data():
            self.record_activity("Save")
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

    def set_word_goal(self):
        if self.current is None:
            return
        try:
            goal = int(self.goal_var.get().strip())
            if not 1 <= goal <= 1000000:
                raise ValueError()
        except ValueError:
            messagebox.showwarning("Word Goal", "Enter a whole number between 1 and 1,000,000.")
            return
        self.store_editor()
        self.current["word_goal"] = goal
        self.update_count()
        if self.save_data():
            self.status.set(f"Word goal set to {goal}.")

    # ---------- Import and recovery ----------
    def import_txt(self):
        path = filedialog.askopenfilename(parent=self, title="Import Text File",
                                          filetypes=[("Text files", "*.txt")])
        if not path:
            return
        try:
            if os.path.getsize(path) > 5 * 1024 * 1024:
                messagebox.showwarning("Import", "Text file exceeds the 5 MB limit.")
                return
            with open(path, "r", encoding="utf-8-sig") as f:
                content = f.read()
        except (OSError, UnicodeError) as exc:
            messagebox.showerror("Import failed", str(exc))
            return
        import_title = os.path.splitext(os.path.basename(path))[0] or "Imported Draft"
        if not self.unique_title(import_title):
            messagebox.showwarning("Duplicate Title", "Another draft already uses this title.")
            return
        article = {"title": import_title,
                   "updated": self.now(), "sections": [{"title": "Introduction", "text": content}]}
        self.articles.append(article)
        if self.save_data():
            self.record_activity("Import", article)
            self.open_article(article)
            self.status.set("Text file imported.")
        else:
            self.articles.remove(article)

    def record_history(self):
        """Keep up to 10 previous manually saved revisions inside articles.json."""
        if self.current is None:
            return
        snapshot = {"date": self.now(), "title": self.current["title"],
                    "sections": copy.deepcopy(self.current["sections"])}
        history = self.current.setdefault("history", [])
        if not history or history[-1]["sections"] != snapshot["sections"] or history[-1]["title"] != snapshot["title"]:
            history.append(snapshot)
            del history[:-10]

    def open_history(self):
        if self.current is None:
            return
        self.store_editor()
        history = self.current.get("history", [])
        if not history:
            messagebox.showinfo("Version History", "No saved revisions yet. Use Save to create one.")
            return
        win = tk.Toplevel(self)
        win.title("Version History")
        win.geometry("460x340")
        win.configure(bg=BG)
        tk.Label(win, text="SAVED REVISIONS (up to 10)", bg=BG, fg=NEON,
                 font=("Helvetica", 12, "bold")).pack(pady=12)
        lst = make_list(win)
        lst.pack(fill="both", expand=True, padx=16, pady=8)
        for i, snap in enumerate(history):
            lst.insert("end", f"{i+1}. {snap['date']}  —  {snap['title']}")
        def restore():
            sel = lst.curselection()
            if not sel:
                messagebox.showinfo("History", "Select a revision first.", parent=win)
                return
            if not messagebox.askyesno("Restore", "Replace current text with this saved revision?", parent=win):
                return
            snapshot = history[sel[0]]
            self.record_history()
            self.current["sections"] = copy.deepcopy(snapshot["sections"])
            self.current["title"] = snapshot["title"]
            self.title_var.set(snapshot["title"])
            self.refresh_sections()
            self.sec_index = None
            self.select_section(0)
            self.current["updated"] = self.now()
            if self.save_data():
                win.destroy()
                self.status.set("Revision restored.")
        FlatButton(win, "Restore Selected", restore, "primary").pack(pady=10)

    def backup_now(self):
        self.store_editor()
        if not self.save_data():
            return
        dest = filedialog.asksaveasfilename(parent=self, title="Save Backup",
                                            defaultextension=".json",
                                            initialfile="quillian-backup-" + time.strftime("%Y%m%d-%H%M%S") + ".json",
                                            filetypes=[("JSON backup", "*.json")])
        if not dest:
            return
        try:
            if os.path.abspath(dest) == os.path.abspath(DATA_FILE):
                raise OSError("Choose a different file from articles.json")
            shutil.copy2(DATA_FILE, dest)
            self.status.set("Backup saved: " + dest)
        except OSError as exc:
            messagebox.showerror("Backup failed", str(exc))

    def on_close(self):
        self.store_editor()
        if not self.save_data() and not messagebox.askyesno(
                "Quit anyway?", "Your latest changes could not be saved. Quit anyway?"):
            return
        self.destroy()


if __name__ == "__main__":
    WritingApp().mainloop()