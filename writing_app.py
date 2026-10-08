

import json
import os
import time
import tkinter as tk
from tkinter import messagebox, simpledialog, filedialog

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "articles.json")


def word_count(text):
    return len(text.split())


class WritingApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Writer")
        self.geometry("1000x620")
        self.minsize(800, 500)

        self.articles = self.load_data()
        self.current = None        # the article being edited #
        self.sec_index = None      # index of the section shown in the editor #

        self.build_nav()
        self.build_dashboard()
        self.build_drafts()
        self.build_editor()
        

        self.status = tk.StringVar(value="Welcome!")
        tk.Label(self, textvariable=self.status, anchor="w", bg="#fdfdfd").pack(
            side="bottom", fill="x")

        self.show("dashboard")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # ---------- data ----------
    def load_data(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return []

    def save_data(self):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(self.articles, f, indent=2)

    def article_words(self, article):
        return sum(word_count(s["text"]) for s in article["sections"])

    # ---------- navigation ----------
    def build_nav(self):
        nav = tk.Frame(self, bg="#1D9100", width=150)
        nav.pack(side="left", fill="y")
        nav.pack_propagate(False)

        tk.Label(nav, text="QUILLIAN", bg="#1D9100", fg="white",
                 font=("Helvetica", 16, "bold")).pack(pady=15)

        for text, cmd in [("Dashboard", lambda: self.show("dashboard")),
                          ("Drafts", lambda: self.show("drafts")),
                          ("Editor", self.go_editor),
                          ("New Article", self.new_article)]:
            tk.Button(nav, text=text, command=cmd, relief="flat",
                      bg="#00720A", fg="white", activebackground="#004100",
                      activeforeground="white", pady=6).pack(fill="x", padx=10, pady=3)

        self.content = tk.Frame(self)
        self.content.pack(side="right", fill="both", expand=True)

    def show(self, name):
        if name != "editor":
            self.store_editor()
        self.frames = {"dashboard": self.dash_frame,
                       "drafts": self.drafts_frame,
                       "editor": self.editor_frame}
        for f in self.frames.values():
            f.pack_forget()
        if name == "dashboard":
            self.refresh_dashboard()
        elif name == "drafts":
            self.refresh_drafts()
        self.frames[name].pack(fill="both", expand=True)

    def go_editor(self):
        if self.current is None:
            messagebox.showinfo("Editor", "Open or create an article first.")
            return
        self.show("editor")

    # ---------- dashboard ----------
    def build_dashboard(self):
        self.dash_frame = tk.Frame(self.content, padx=20, pady=20)
        tk.Label(self.dash_frame, text="Dashboard",
                 font=("Helvetica", 20, "bold")).pack(anchor="w")

        self.stat_vars = {k: tk.StringVar() for k in ("total", "drafts", "published", "words")}
        stats = tk.Frame(self.dash_frame)
        stats.pack(fill="x", pady=15)
        for i, (key, label) in enumerate([("total", "Articles"), ("drafts", "Drafts"),
                                          ("published", "Published"), ("words", "Total words")]):
            box = tk.Frame(stats, bd=1, relief="solid", padx=20, pady=10)
            box.grid(row=0, column=i, padx=6)
            tk.Label(box, textvariable=self.stat_vars[key],
                     font=("Helvetica", 22, "bold")).pack()
            tk.Label(box, text=label).pack()

        tk.Label(self.dash_frame, text="Recently edited",
                 font=("Helvetica", 13, "bold")).pack(anchor="w", pady=(10, 4))
        self.recent_list = tk.Listbox(self.dash_frame, height=8)
        self.recent_list.pack(fill="x")
        self.recent_list.bind("<Double-Button-1>", lambda e: self.open_recent())

        row = tk.Frame(self.dash_frame)
        row.pack(anchor="w", pady=10)
        tk.Button(row, text="Open Selected", command=self.open_recent).pack(side="left", padx=(0, 6))
        tk.Button(row, text="New Article", command=self.new_article).pack(side="left")

    def recent_articles(self):
        return sorted(self.articles, key=lambda a: a["updated"], reverse=True)[:8]

    def refresh_dashboard(self):
        drafts = sum(1 for a in self.articles if a["status"] == "draft")
        self.stat_vars["total"].set(len(self.articles))
        self.stat_vars["drafts"].set(drafts)
        self.stat_vars["published"].set(len(self.articles) - drafts)
        self.stat_vars["words"].set(sum(self.article_words(a) for a in self.articles))

        self.recent_list.delete(0, "end")
        for a in self.recent_articles():
            self.recent_list.insert("end", f"{a['title']}  -  {a['status']}  -  {a['updated']}")

    def open_recent(self):
        sel = self.recent_list.curselection()
        if not sel:
            messagebox.showinfo("Open", "Select an article first.")
            return
        self.open_article(self.recent_articles()[sel[0]])

    # ---------- drafts ----------
    def build_drafts(self):
        self.drafts_frame = tk.Frame(self.content, padx=20, pady=20)
        tk.Label(self.drafts_frame, text="Drafts & Articles",
                 font=("Helvetica", 20, "bold")).pack(anchor="w")

        self.drafts_list = tk.Listbox(self.drafts_frame)
        self.drafts_list.pack(fill="both", expand=True, pady=10)
        self.drafts_list.bind("<Double-Button-1>", lambda e: self.open_selected_draft())

        row = tk.Frame(self.drafts_frame)
        row.pack(anchor="w")
        for text, cmd in [("New", self.new_article),
                          ("Open", self.open_selected_draft),
                          ("Toggle Draft/Published", self.toggle_status),
                          ("Delete", self.delete_article)]:
            tk.Button(row, text=text, command=cmd).pack(side="left", padx=(0, 6))

    def refresh_drafts(self):
        self.drafts_list.delete(0, "end")
        for a in self.articles:
            self.drafts_list.insert(
                "end", f"{a['title']}  [{a['status']}]  {self.article_words(a)} words")

    def selected_article(self):
        sel = self.drafts_list.curselection()
        if not sel:
            messagebox.showinfo("Select", "Select an article first.")
            return None
        return self.articles[sel[0]]

    def open_selected_draft(self):
        a = self.selected_article()
        if a:
            self.open_article(a)

    def toggle_status(self):
        a = self.selected_article()
        if a:
            a["status"] = "published" if a["status"] == "draft" else "draft"
            self.save_data()
            self.refresh_drafts()
            self.status.set(f"'{a['title']}' is now {a['status']}.")

    def delete_article(self):
        a = self.selected_article()
        if a and messagebox.askyesno("Delete", f"Delete '{a['title']}'?"):
            if a is self.current:
                self.current = None
                self.sec_index = None
            self.articles.remove(a)
            self.save_data()
            self.refresh_drafts()
            self.status.set("Article deleted.")

    # ---------- editor ----------
    def build_editor(self):
        self.editor_frame = tk.Frame(self.content)

        # top bar: title + buttons
        top = tk.Frame(self.editor_frame, padx=10, pady=8)
        top.pack(fill="x")
        tk.Label(top, text="Title:").pack(side="left")
        self.title_var = tk.StringVar()
        tk.Entry(top, textvariable=self.title_var, font=("Helvetica", 14)).pack(
            side="left", fill="x", expand=True, padx=6)
        tk.Button(top, text="Save", command=self.save_article).pack(side="left", padx=2)
        tk.Button(top, text="Export .txt", command=self.export_article).pack(side="left", padx=2)

        body = tk.Frame(self.editor_frame)
        body.pack(fill="both", expand=True)

        # side panel: sections
        side = tk.Frame(body, padx=10, pady=5)
        side.pack(side="left", fill="y")
        tk.Label(side, text="Sections", font=("Helvetica", 12, "bold")).pack(anchor="w")
        self.sec_list = tk.Listbox(side, width=24, exportselection=False)
        self.sec_list.pack(fill="y", expand=True, pady=4)
        self.sec_list.bind("<<ListboxSelect>>", self.on_section_select)
        for text, cmd in [("Add Section", self.add_section),
                          ("Rename", self.rename_section),
                          ("Move Up", lambda: self.move_section(-1)),
                          ("Move Down", lambda: self.move_section(1)),
                          ("Delete Section", self.delete_section)]:
            tk.Button(side, text=text, command=cmd).pack(fill="x", pady=1)

        # text area
        right = tk.Frame(body, padx=5, pady=5)
        right.pack(side="left", fill="both", expand=True)
        self.sec_label = tk.Label(right, text="", font=("Helvetica", 12, "bold"))
        self.sec_label.pack(anchor="w")
        scroll = tk.Scrollbar(right)
        scroll.pack(side="right", fill="y")
        self.text = tk.Text(right, wrap="word", undo=True, font=("Georgia", 12),
                            yscrollcommand=scroll.set)
        self.text.pack(fill="both", expand=True)
        scroll.config(command=self.text.yview)
        self.text.bind("<KeyRelease>", lambda e: self.update_count())
        self.count_var = tk.StringVar()
        tk.Label(right, textvariable=self.count_var, anchor="e").pack(fill="x")

    def new_article(self):
        title = simpledialog.askstring("New Article", "Article title:", parent=self)
        if not title:
            return
        article = {"title": title.strip() or "Untitled", "status": "draft",
                   "updated": time.strftime("%Y-%m-%d %H:%M"),
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
            self.sec_list.insert("end", s["title"])

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
        if not sel or self.current is None:
            return
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
            messagebox.showinfo("Delete Section", "An article needs at least one section.")
            return
        if messagebox.askyesno("Delete Section", f"Delete '{sections[self.sec_index]['title']}'?"):
            del sections[self.sec_index]
            self.refresh_sections()
            self.sec_index = None
            self.select_section(0)

    def save_article(self):
        if self.current is None:
            return
        self.store_editor()
        self.current["updated"] = time.strftime("%Y-%m-%d %H:%M")
        self.save_data()
        self.status.set(f"Saved at {time.strftime('%H:%M:%S')}")

    def export_article(self):
        if self.current is None:
            return
        self.store_editor()
        path = filedialog.asksaveasfilename(
            defaultextension=".txt", initialfile=self.current["title"] + ".txt",
            filetypes=[("Text files", "*.txt")])
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.current["title"] + "\n" + "=" * len(self.current["title"]) + "\n\n")
            for s in self.current["sections"]:
                f.write(s["title"] + "\n" + "-" * len(s["title"]) + "\n" + s["text"] + "\n\n")
        self.status.set(f"Exported to {path}")

    def on_close(self):
        self.store_editor()
        self.save_data()
        self.destroy()


if __name__ == "__main__":
    WritingApp().mainloop()
