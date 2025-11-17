import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser

from PIL import Image, ImageDraw, ImageFont, ImageTk


SUPPORTED_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff")

POSITION_MODES = {
    "Слева сверху": "lt",
    "Справа сверху": "rt",
    "Слева снизу": "lb",
    "Справа снизу": "rb",
    "По центру": "center",
    "Произвольно": "custom",
}
CODE_TO_DISPLAY = {v: k for k, v in POSITION_MODES.items()}


class ImageNumberingApp:
    def __init__(self, master):
        self.master = master
        self.master.title("Нумерация изображений")

        # Минимальные размеры окна по умолчанию
        self.master.minsize(900, 600)

        # Цвета интерфейса
        self.primary_color = "#4C7EF3"
        self.danger_color = "#D93025"
        self.background_color = "#F5F6FA"

        # Стили для более современного вида
        style = ttk.Style(self.master)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        self._configure_styles(style)

        # Безопасная настройка шрифта (без пробелов в названии)
        try:
            self.master.option_add("*Font", "TkDefaultFont 10")
        except tk.TclError:
            pass

        self.master.configure(bg=self.background_color)

        self.image_paths = []
        self.image_sizes = []  # (w, h) для отображения в списке
        self.index_to_number = {}

        self.current_folder = None
        self.font_path = None
        self.output_folder = None  # папка для сохранения

        # Предпросмотр
        self.preview_image_tk = None
        self.preview_scale = 1.0
        self.current_original_size = None
        self.canvas_width = 800
        self.canvas_height = 500
        self.canvas_image_id = None

        # Панорамирование
        self.pan_offset_x = 0
        self.pan_offset_y = 0
        self.is_panning = False
        self.pan_start_x = 0
        self.pan_start_y = 0
        self.mouse_down_x = 0
        self.mouse_down_y = 0
        self.mouse_moved = False
        self.last_center_x = None
        self.last_center_y = None

        # Параметры нумерации
        self.skip_first_var = tk.StringVar(value="0")
        self.skip_last_var = tk.StringVar(value="0")
        self.exclude_list_var = tk.StringVar(value="")
        self.start_from_image_var = tk.StringVar(value="1")

        # Параметры шрифта
        self.font_size_var = tk.StringVar(value="72")

        # Цвет текста
        self.text_color = (0, 0, 0)
        self.text_color_hex = "#000000"

        # Положение (общий режим + отступы)
        self.position_mode_var = tk.StringVar(value="rb")  # внутренний код
        self.position_display_var = tk.StringVar(
            value=CODE_TO_DISPLAY.get("rb", "Справа снизу")
        )
        self.margin_x_var = tk.StringVar(value="50")
        self.margin_y_var = tk.StringVar(value="50")

        # Ручные номера для отдельных страниц
        self.manual_start_numbers = {}  # idx -> явный номер
        self.manual_number_var = tk.StringVar(value="")

        # Индивидуальные пропуски
        self.per_image_skip = set()
        self.skip_current_var = tk.BooleanVar(value=False)

        # Индивидуальные позиции (x, y) в координатах оригинального изображения
        self.custom_positions = {}  # idx -> (x, y)

        # Масштаб предпросмотра
        self.zoom_var = tk.DoubleVar(value=1.0)

        self.listbox_default_fg = "#1F1F1F"

        self._build_ui()
        self._setup_keyboard_shortcuts()

    def _configure_styles(self, style: ttk.Style):
        """Настройка базовых стилей приложения."""
        style.configure("TFrame", background=self.background_color)
        style.configure("TLabelframe", background=self.background_color)
        style.configure("TLabelframe.Label", background=self.background_color)
        style.configure("TLabel", background=self.background_color)
        style.configure("TCheckbutton", background=self.background_color)

        style.configure(
            "Accent.TButton",
            padding=(12, 8),
            background=self.primary_color,
            foreground="white",
            font=("Segoe UI", 10, "bold"),
            borderwidth=0,
        )
        style.map(
            "Accent.TButton",
            background=[("active", "#3456B8"), ("disabled", "#A0A8C0")],
            foreground=[("disabled", "#E1E1E1")],
        )

        style.configure("TButton", padding=6)
        style.configure(
            "Skip.TCheckbutton",
            background=self.background_color,
            foreground=self.danger_color,
            font=("Segoe UI", 10, "bold"),
        )

    def _build_ui(self):
        # Верхняя панель - выбор папки
        top_frame = ttk.Frame(self.master)
        top_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        folder_btn = ttk.Button(
            top_frame,
            text="Выбрать папку с изображениями",
            command=self.choose_folder,
            style="Accent.TButton",
        )
        folder_btn.pack(side=tk.LEFT)

        self.folder_label = ttk.Label(top_frame, text="Папка не выбрана")
        self.folder_label.pack(side=tk.LEFT, padx=10)

        # Основная область: список файлов и предпросмотр
        main_frame = ttk.Frame(self.master)
        main_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Список изображений
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(side=tk.LEFT, fill=tk.Y)

        list_label = ttk.Label(
            list_frame,
            text="Изображения (№ | имя файла (ШxВ))",
            font=("Segoe UI", 10, "bold"),
        )
        list_label.pack(anchor="w")

        list_inner = ttk.Frame(list_frame)
        list_inner.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.listbox = tk.Listbox(
            list_inner,
            width=45,
            exportselection=False,
            font=("Segoe UI", 10),
            activestyle="none",
            bg="#FFFFFF",
            fg=self.listbox_default_fg,
            selectbackground=self.primary_color,
            selectforeground="white",
            relief="flat",
            bd=1,
            highlightthickness=1,
            highlightcolor="#d0d7e2",
            highlightbackground="#d0d7e2",
        )
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(list_inner, orient=tk.VERTICAL, command=self.listbox.yview)
        scrollbar.pack(side=tk.LEFT, fill=tk.Y)
        self.listbox.config(yscrollcommand=scrollbar.set)

        self.listbox.bind("<<ListboxSelect>>", lambda event: self.update_preview())

        skip_cb = ttk.Checkbutton(
            list_frame,
            text="Пропустить это изображение",
            variable=self.skip_current_var,
            command=self.on_toggle_skip_current,
            style="Skip.TCheckbutton",
        )
        skip_cb.pack(anchor="w", pady=5)

        ttk.Label(
            list_frame,
            text="Горячие клавиши: ← / → / Enter — переключение изображения",
            wraplength=220,
            foreground="#4A4A4A",
        ).pack(anchor="w", pady=(0, 5))

        # Предпросмотр
        preview_outer = ttk.Frame(main_frame)
        preview_outer.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)

        preview_label_top = ttk.Label(
            preview_outer,
            text=(
                "Предпросмотр: колесо мыши — зум, перетаскивание ЛКМ — панорамирование,"
                " клик ЛКМ без движения — задать позицию номера."
                " Также доступны клавиши ← / → / Enter для переключения изображений."
            ),
            wraplength=600,
            justify="left",
        )
        preview_label_top.pack(anchor="w")

        # Canvas, растягивающийся по размеру окна
        self.preview_canvas = tk.Canvas(
            preview_outer,
            bg="gray",
            highlightthickness=1,
            relief="sunken",
        )
        self.preview_canvas.pack(fill=tk.BOTH, expand=True, pady=5)

        self.preview_canvas.bind("<Configure>", self.on_canvas_resize)

        # События для панорамирования и клика
        self.preview_canvas.bind("<ButtonPress-1>", self.on_canvas_button_press)
        self.preview_canvas.bind("<B1-Motion>", self.on_canvas_motion)
        self.preview_canvas.bind("<ButtonRelease-1>", self.on_canvas_button_release)

        # Зум колесом мыши
        self.preview_canvas.bind("<MouseWheel>", self.on_mouse_wheel)   # Windows / Mac
        self.preview_canvas.bind("<Button-4>", self.on_mouse_wheel)     # Linux up
        self.preview_canvas.bind("<Button-5>", self.on_mouse_wheel)     # Linux down

        self.preview_info_label = ttk.Label(preview_outer, text="Номер для выбранного изображения: -")
        self.preview_info_label.pack(anchor="w", pady=5)

        # Блок ручного номера и позиции
        manual_frame = ttk.Frame(preview_outer)
        manual_frame.pack(anchor="w", pady=5, fill=tk.X)

        ttk.Label(manual_frame, text="Номер для этого изображения:").pack(side=tk.LEFT)

        manual_entry = ttk.Entry(manual_frame, textvariable=self.manual_number_var, width=6)
        manual_entry.pack(side=tk.LEFT, padx=3)

        manual_apply_btn = ttk.Button(
            manual_frame,
            text="Применить",
            command=self.set_manual_number_for_current,
            style="Accent.TButton",
        )
        manual_apply_btn.pack(side=tk.LEFT, padx=3)

        manual_reset_btn = ttk.Button(
            manual_frame,
            text="Сбросить",
            command=self.reset_manual_number_for_current,
            style="Accent.TButton",
        )
        manual_reset_btn.pack(side=tk.LEFT, padx=3)

        pos_reset_btn = ttk.Button(
            manual_frame,
            text="Сброс позиции",
            command=self.reset_position_for_current,
            style="Accent.TButton",
        )
        pos_reset_btn.pack(side=tk.LEFT, padx=3)

        # Масштаб
        zoom_frame = ttk.Frame(preview_outer)
        zoom_frame.pack(anchor="w", pady=5, fill=tk.X)

        ttk.Label(zoom_frame, text="Масштаб:").pack(side=tk.LEFT)

        zoom_out_btn = ttk.Button(
            zoom_frame,
            text="-",
            width=2,
            command=lambda: self.change_zoom(0.8),
            style="Accent.TButton",
        )
        zoom_out_btn.pack(side=tk.LEFT, padx=2)

        zoom_scale = ttk.Scale(
            zoom_frame,
            from_=0.2,
            to=3.0,
            orient="horizontal",
            variable=self.zoom_var,
            command=self.on_zoom_change
        )
        zoom_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        zoom_in_btn = ttk.Button(
            zoom_frame,
            text="+",
            width=2,
            command=lambda: self.change_zoom(1.25),
            style="Accent.TButton",
        )
        zoom_in_btn.pack(side=tk.LEFT, padx=2)

        update_preview_btn = ttk.Button(
            preview_outer,
            text="Обновить предпросмотр",
            command=self.update_preview,
            style="Accent.TButton",
        )
        update_preview_btn.pack(anchor="e", pady=5)

        # Нижняя часть: настройки
        bottom_frame = ttk.Frame(self.master)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)

        # Левая часть настроек: шрифт и положение
        left_settings = ttk.Frame(bottom_frame)
        left_settings.pack(side=tk.LEFT, fill=tk.X, expand=True)

        font_frame = ttk.Labelframe(left_settings, text="Шрифт и цвет")
        font_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        font_btn = ttk.Button(
            font_frame,
            text="Выбрать TTF шрифт",
            command=self.choose_font,
            style="Accent.TButton",
        )
        font_btn.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        self.font_label = ttk.Label(font_frame, text="Шрифт не выбран (будет использован стандартный)")
        self.font_label.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(font_frame, text="Размер шрифта:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        font_size_entry = ttk.Entry(font_frame, textvariable=self.font_size_var, width=6)
        font_size_entry.grid(row=1, column=1, padx=5, pady=5, sticky="w")

        color_btn = ttk.Button(
            font_frame,
            text="Цвет текста",
            command=self.choose_text_color,
            style="Accent.TButton",
        )
        color_btn.grid(row=2, column=0, padx=5, pady=5, sticky="e")

        self.color_label = ttk.Label(font_frame, text="Цвет: чёрный")
        self.color_label.grid(row=2, column=1, padx=5, pady=5, sticky="w")

        position_frame = ttk.Labelframe(left_settings, text="Общее положение текста")
        position_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        ttk.Label(position_frame, text="Расположение:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        pos_combo = ttk.Combobox(
            position_frame,
            textvariable=self.position_display_var,
            state="readonly",
            values=list(POSITION_MODES.keys()),
            width=18,
        )
        pos_combo.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        pos_combo.bind("<<ComboboxSelected>>", self.on_position_mode_changed)

        ttk.Label(position_frame, text="Отступ X (для углов / центр):").grid(
            row=1, column=0, padx=5, pady=5, sticky="e"
        )
        margin_x_entry = ttk.Entry(position_frame, textvariable=self.margin_x_var, width=6)
        margin_x_entry.grid(row=1, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(position_frame, text="Отступ Y (для углов / центр):").grid(
            row=2, column=0, padx=5, pady=5, sticky="e"
        )
        margin_y_entry = ttk.Entry(position_frame, textvariable=self.margin_y_var, width=6)
        margin_y_entry.grid(row=2, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(position_frame, text="Индивидуальная позиция задаётся кликом по предпросмотру").grid(
            row=3, column=0, columnspan=2, padx=5, pady=5, sticky="w"
        )

        # Правая часть настроек: нумерация
        right_settings = ttk.Frame(bottom_frame)
        right_settings.pack(side=tk.LEFT, fill=tk.X, expand=True)

        number_frame = ttk.Labelframe(right_settings, text="Нумерация и исключения")
        number_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        ttk.Label(number_frame, text="Пропустить первые N изображений:").grid(
            row=0, column=0, padx=5, pady=2, sticky="e"
        )
        skip_first_entry = ttk.Entry(number_frame, textvariable=self.skip_first_var, width=6)
        skip_first_entry.grid(row=0, column=1, padx=5, pady=2, sticky="w")

        ttk.Label(number_frame, text="Пропустить последние M изображений:").grid(
            row=1, column=0, padx=5, pady=2, sticky="e"
        )
        skip_last_entry = ttk.Entry(number_frame, textvariable=self.skip_last_var, width=6)
        skip_last_entry.grid(row=1, column=1, padx=5, pady=2, sticky="w")

        ttk.Label(number_frame, text="Явные исключения (индексы, напр. 1,2,10-15):").grid(
            row=2, column=0, padx=5, pady=2, sticky="e"
        )
        exclude_entry = ttk.Entry(number_frame, textvariable=self.exclude_list_var, width=25)
        exclude_entry.grid(row=2, column=1, padx=5, pady=2, sticky="w")

        ttk.Label(number_frame, text="Начать нумерацию с изображения №:").grid(
            row=3, column=0, padx=5, pady=2, sticky="e"
        )
        start_from_entry = ttk.Entry(number_frame, textvariable=self.start_from_image_var, width=6)
        start_from_entry.grid(row=3, column=1, padx=5, pady=2, sticky="w")

        self.status_label = ttk.Label(right_settings, text="Готово.")
        self.status_label.pack(side=tk.TOP, anchor="w", padx=5, pady=5)

        save_folder_btn = ttk.Button(
            right_settings,
            text="Папка для сохранения...",
            command=self.choose_output_folder,
            style="Accent.TButton",
        )
        save_folder_btn.pack(side=tk.LEFT, padx=5, pady=5)

        self.output_folder_label = ttk.Label(
            right_settings,
            text="Папка сохранения: не выбрана"
        )
        self.output_folder_label.pack(side=tk.LEFT, padx=5, pady=5)

        apply_btn = ttk.Button(
            right_settings,
            text="Применить ко всем изображениям",
            command=self.apply_to_all,
            style="Accent.TButton",
        )
        apply_btn.pack(side=tk.RIGHT, padx=5, pady=5)

    def _setup_keyboard_shortcuts(self):
        self.master.bind_all("<Left>", self.on_prev_image, add="+")
        self.master.bind_all("<Right>", self.on_next_image, add="+")
        self.master.bind_all("<Return>", self.on_enter_navigate, add="+")

    def _should_ignore_navigation_shortcut(self, event, allow_listbox=False):
        if event is None:
            return False
        widget = event.widget
        if widget is None:
            return False
        if isinstance(widget, (tk.Entry, tk.Text)):
            return True
        widget_class = widget.winfo_class()
        ignored_classes = {"TEntry", "Entry", "TCombobox", "TSpinbox", "Spinbox", "TButton"}
        if widget_class in ignored_classes:
            return True
        if not allow_listbox and isinstance(widget, tk.Listbox):
            return True
        return False

    def navigate_images(self, offset):
        if not self.image_paths:
            return
        selection = self.listbox.curselection()
        if selection:
            current_idx = selection[0]
        else:
            current_idx = 0
        new_idx = max(0, min(current_idx + offset, len(self.image_paths) - 1))
        if new_idx == current_idx:
            return
        self.listbox.selection_clear(0, tk.END)
        self.listbox.selection_set(new_idx)
        self.listbox.activate(new_idx)
        self.listbox.see(new_idx)
        self.update_preview()

    def on_prev_image(self, event=None):
        if event and self._should_ignore_navigation_shortcut(event):
            return
        self.navigate_images(-1)

    def on_next_image(self, event=None):
        if event and self._should_ignore_navigation_shortcut(event):
            return
        self.navigate_images(1)

    def on_enter_navigate(self, event=None):
        if event and self._should_ignore_navigation_shortcut(event, allow_listbox=True):
            return
        self.navigate_images(1)

    # --- Вспомогательные методы ---

    def choose_folder(self):
        folder = filedialog.askdirectory()
        if not folder:
            return
        self.current_folder = folder
        self.folder_label.config(text=folder)

        # дефолтная папка для сохранения — подкаталог numbered
        self.output_folder = os.path.join(folder, "numbered")
        os.makedirs(self.output_folder, exist_ok=True)
        if hasattr(self, "output_folder_label"):
            self.update_output_folder_label()

        self.load_images_from_folder(folder)

    def load_images_from_folder(self, folder):
        self.image_paths = []
        self.image_sizes = []
        self.index_to_number.clear()
        self.manual_start_numbers.clear()
        self.manual_number_var.set("")
        self.per_image_skip.clear()
        self.custom_positions.clear()
        self.listbox.delete(0, tk.END)

        for name in sorted(os.listdir(folder)):
            if name.lower().endswith(SUPPORTED_EXTENSIONS):
                full_path = os.path.join(folder, name)
                self.image_paths.append(full_path)
                try:
                    with Image.open(full_path) as im:
                        self.image_sizes.append(im.size)
                except Exception:
                    self.image_sizes.append(None)

        if not self.image_paths:
            messagebox.showwarning("Предупреждение", "В выбранной папке нет поддерживаемых изображений.")
            self.preview_canvas.delete("all")
            self.canvas_image_id = None
            return

        self.recalculate_numbering()
        self.refresh_listbox_display(keep_selection=False, keep_view=False)
        self.update_preview()

    def choose_font(self):
        font_file = filedialog.askopenfilename(
            title="Выберите TTF шрифт",
            filetypes=[("TrueType шрифты", "*.ttf *.otf"), ("Все файлы", "*.*")],
        )
        if not font_file:
            return
        self.font_path = font_file
        self.font_label.config(text=os.path.basename(font_file))
        self.update_preview()

    def choose_text_color(self):
        color = colorchooser.askcolor(initialcolor=self.text_color_hex)
        if not color or color[1] is None:
            return
        r, g, b = color[0]
        self.text_color = (int(r), int(g), int(b))
        self.text_color_hex = color[1]
        self.color_label.config(text=f"Цвет: {self.text_color_hex}", foreground=self.text_color_hex)
        self.update_preview()

    def parse_int(self, value, default=0):
        try:
            return int(value)
        except Exception:
            return default

    def parse_exclude_list(self, text):
        text = text.replace(" ", "")
        if not text:
            return set()
        result = set()
        parts = text.split(",")
        for part in parts:
            if not part:
                continue
            if "-" in part:
                sub = part.split("-", 1)
                if len(sub) != 2:
                    continue
                start, end = sub
                if start.isdigit() and end.isdigit():
                    a = int(start)
                    b = int(end)
                    if a <= b:
                        for v in range(a, b + 1):
                            result.add(v)
            else:
                if part.isdigit():
                    result.add(int(part))
        return result

    def recalculate_numbering(self):
        self.index_to_number.clear()
        n = len(self.image_paths)
        if n == 0:
            return

        skip_first = max(0, self.parse_int(self.skip_first_var.get(), 0))
        skip_last = max(0, self.parse_int(self.skip_last_var.get(), 0))
        manual_exclude = self.parse_exclude_list(self.exclude_list_var.get())
        start_from = self.parse_int(self.start_from_image_var.get(), 1)
        if start_from < 1:
            start_from = 1

        included_indices = []
        for idx in range(n):
            p = idx + 1  # человеческий индекс (1..N)
            excluded = False

            if p <= skip_first:
                excluded = True
            if p > n - skip_last:
                excluded = True
            if p in manual_exclude:
                excluded = True
            if p < start_from:
                excluded = True
            if idx in self.per_image_skip:
                excluded = True

            if not excluded:
                included_indices.append(idx)

        current_number = None
        for idx in included_indices:
            if idx in self.manual_start_numbers:
                current_number = self.manual_start_numbers[idx]
            else:
                if current_number is None:
                    current_number = 1
                else:
                    current_number += 1

            self.index_to_number[idx] = current_number

    def refresh_listbox_display(self, keep_selection=True, keep_view=True):
        prev_idx = 0
        sel = self.listbox.curselection()
        if keep_selection and sel:
            prev_idx = sel[0]

        prev_view_start = 0.0
        if keep_view:
            try:
                prev_view_start = self.listbox.yview()[0]
            except tk.TclError:
                prev_view_start = 0.0

        self.listbox.delete(0, tk.END)

        for idx, path in enumerate(self.image_paths):
            num = self.index_to_number.get(idx)
            if num is None:
                num_str = "  - "
            else:
                num_str = f"{num:4d}"
            base = os.path.basename(path)

            size_str = ""
            if idx < len(self.image_sizes) and self.image_sizes[idx] is not None:
                w, h = self.image_sizes[idx]
                size_str = f" ({w}x{h})"

            text = f"{num_str} | {base}{size_str}"
            self.listbox.insert(tk.END, text)
            inserted_index = self.listbox.size() - 1
            if idx in self.per_image_skip:
                self.listbox.itemconfig(inserted_index, foreground=self.danger_color)
            else:
                self.listbox.itemconfig(inserted_index, foreground=self.listbox_default_fg)

        if self.image_paths:
            if keep_selection:
                idx_to_select = min(prev_idx, len(self.image_paths) - 1)
            else:
                idx_to_select = 0
            self.listbox.selection_clear(0, tk.END)
            self.listbox.selection_set(idx_to_select)
            self.listbox.activate(idx_to_select)
            self.listbox.see(idx_to_select)

        if keep_view:
            try:
                self.listbox.yview_moveto(prev_view_start)
            except tk.TclError:
                pass

    def get_font(self):
        size = self.parse_int(self.font_size_var.get(), 72)
        if size <= 0:
            size = 72
        if self.font_path:
            try:
                return ImageFont.truetype(self.font_path, size)
            except Exception:
                pass
        return ImageFont.load_default()

    def compute_position(self, idx, img_w, img_h, text_w, text_h):
        # Индивидуальная позиция имеет приоритет
        if idx in self.custom_positions:
            x, y = self.custom_positions[idx]
        else:
            mode = self.position_mode_var.get()
            margin_x = self.parse_int(self.margin_x_var.get(), 50)
            margin_y = self.parse_int(self.margin_y_var.get(), 50)

            if mode == "lt":
                x = margin_x
                y = margin_y
            elif mode == "rt":
                x = img_w - text_w - margin_x
                y = margin_y
            elif mode == "lb":
                x = margin_x
                y = img_h - text_h - margin_y
            elif mode == "rb":
                x = img_w - text_w - margin_x
                y = img_h - text_h - margin_y
            elif mode == "center":
                x = (img_w - text_w) // 2 + margin_x
                y = (img_h - text_h) // 2 + margin_y
            elif mode == "custom":
                # если режим «Произвольно», но индивидуальная позиция не задана —
                # используем правый нижний с отступами
                x = img_w - text_w - margin_x
                y = img_h - text_h - margin_y
            else:
                x = img_w - text_w - margin_x
                y = img_h - text_h - margin_y

        x = max(0, min(int(x), img_w - text_w))
        y = max(0, min(int(y), img_h - text_h))
        return x, y

    def draw_number_on_image(self, idx, image, number):
        if number is None:
            return image

        font = self.get_font()
        draw = ImageDraw.Draw(image)

        text = str(number)

        # Измерение текста
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
        except AttributeError:
            text_w, text_h = draw.textsize(text, font=font)

        x, y = self.compute_position(idx, image.width, image.height, text_w, text_h)

        # Цвет текста и обводка
        r, g, b = self.text_color
        brightness = (r * 299 + g * 587 + b * 114) / 1000
        if brightness < 128:
            outline_color = (255, 255, 255)
        else:
            outline_color = (0, 0, 0)

        fill_main = self.text_color
        fill_outline = outline_color

        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                draw.text((x + dx, y + dy), text, font=font, fill=fill_outline)

        draw.text((x, y), text, font=font, fill=fill_main)
        return image

    def update_preview(self):
        if not self.image_paths:
            return

        selection = self.listbox.curselection()
        if not selection:
            idx = 0
            if self.image_paths:
                self.listbox.selection_set(0)
        else:
            idx = selection[0]

        if idx < 0 or idx >= len(self.image_paths):
            return

        # Пересчёт нумерации и обновление списка
        self.recalculate_numbering()
        self.refresh_listbox_display(keep_selection=True)

        # ещё раз уточняем выбранный индекс
        selection = self.listbox.curselection()
        if not selection:
            idx = 0
            if self.image_paths:
                self.listbox.selection_set(0)
        else:
            idx = selection[0]

        if idx < 0 or idx >= len(self.image_paths):
            return

        path = self.image_paths[idx]
        number = self.index_to_number.get(idx)
        if number is None:
            self.preview_info_label.config(
                text=f"Изображение #{idx + 1}: исключено из нумерации."
            )
        else:
            self.preview_info_label.config(
                text=f"Изображение #{idx + 1}: номер будет {number}."
            )

        # Обновляем чекбокс пропуска
        self.skip_current_var.set(idx in self.per_image_skip)

        try:
            with Image.open(path) as im:
                im = im.convert("RGBA")
                im_for_preview = im.copy()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось открыть изображение:\n{e}")
            return

        im_for_preview = self.draw_number_on_image(idx, im_for_preview, number)

        orig_w, orig_h = im_for_preview.size
        self.current_original_size = (orig_w, orig_h)

        # базовый масштаб под текущий размер canvas
        base_scale = min(
            self.canvas_width / orig_w if orig_w else 1.0,
            self.canvas_height / orig_h if orig_h else 1.0,
            1.0,
        )
        scale = base_scale * self.zoom_var.get()
        if scale <= 0:
            scale = 0.01
        self.preview_scale = scale

        new_size = (max(1, int(orig_w * scale)), max(1, int(orig_h * scale)))
        resized = im_for_preview.resize(new_size, Image.LANCZOS)

        self.preview_image_tk = ImageTk.PhotoImage(resized)

        center_x = self.canvas_width // 2 + self.pan_offset_x
        center_y = self.canvas_height // 2 + self.pan_offset_y

        self.preview_canvas.delete("all")
        self.canvas_image_id = self.preview_canvas.create_image(
            center_x, center_y, image=self.preview_image_tk
        )

        self.last_center_x = center_x
        self.last_center_y = center_y

        # Обновляем поле ручного номера
        if idx in self.manual_start_numbers:
            self.manual_number_var.set(str(self.manual_start_numbers[idx]))
        else:
            self.manual_number_var.set("")

    # --- События canvas: изменение размера, панорамирование и клик ---

    def on_canvas_resize(self, event):
        # обновляем текущие размеры canvas и перерисовываем
        self.canvas_width = max(50, event.width)
        self.canvas_height = max(50, event.height)
        self.update_preview()

    def on_canvas_button_press(self, event):
        self.is_panning = True
        self.mouse_down_x = event.x
        self.mouse_down_y = event.y
        self.pan_start_x = self.pan_offset_x
        self.pan_start_y = self.pan_offset_y
        self.mouse_moved = False

    def on_canvas_motion(self, event):
        if not self.is_panning or self.canvas_image_id is None:
            return
        dx = event.x - self.mouse_down_x
        dy = event.y - self.mouse_down_y
        if abs(dx) > 3 or abs(dy) > 3:
            self.mouse_moved = True

        self.pan_offset_x = self.pan_start_x + dx
        self.pan_offset_y = self.pan_start_y + dy

        center_x = self.canvas_width // 2 + self.pan_offset_x
        center_y = self.canvas_height // 2 + self.pan_offset_y
        self.preview_canvas.coords(self.canvas_image_id, center_x, center_y)
        self.last_center_x = center_x
        self.last_center_y = center_y

    def on_canvas_button_release(self, event):
        if not self.is_panning:
            return
        self.is_panning = False

        # Если не было значимого движения — считаем это кликом для установки позиции номера
        if not self.mouse_moved:
            self.on_preview_click(event)

    def on_preview_click(self, event):
        if not self.current_original_size or self.canvas_image_id is None:
            return
        selection = self.listbox.curselection()
        if not selection:
            return
        idx = selection[0]

        orig_w, orig_h = self.current_original_size
        scale = self.preview_scale if self.preview_scale else 1.0

        cx = self.last_center_x
        cy = self.last_center_y

        dx = event.x - cx
        dy = event.y - cy

        img_x = dx / scale + orig_w / 2
        img_y = dy / scale + orig_h / 2

        img_x = max(0, min(int(img_x), orig_w - 1))
        img_y = max(0, min(int(img_y), orig_h - 1))

        self.custom_positions[idx] = (img_x, img_y)
        self.update_preview()

    # --- Зум ---

    def change_zoom(self, factor):
        z = self.zoom_var.get() * factor
        if z < 0.2:
            z = 0.2
        if z > 3.0:
            z = 3.0
        self.zoom_var.set(z)
        self.update_preview()

    def on_zoom_change(self, event=None):
        self.update_preview()

    def on_mouse_wheel(self, event):
        # Windows / Mac
        if hasattr(event, "delta") and event.delta != 0:
            factor = 1.1 if event.delta > 0 else 0.9
        else:
            # Linux
            if event.num == 4:
                factor = 1.1
            elif event.num == 5:
                factor = 0.9
            else:
                return
        self.change_zoom(factor)

    # --- Остальные кнопки/действия ---

    def reset_position_for_current(self):
        selection = self.listbox.curselection()
        if not selection:
            return
        idx = selection[0]
        if idx in self.custom_positions:
            del self.custom_positions[idx]
        self.update_preview()

    def update_output_folder_label(self):
        if self.output_folder:
            self.output_folder_label.config(text=f"Папка сохранения: {self.output_folder}")
        else:
            self.output_folder_label.config(text="Папка сохранения: не выбрана")

    def choose_output_folder(self):
        if not self.current_folder:
            messagebox.showwarning("Предупреждение", "Сначала выберите папку с изображениями.")
            return

        folder = filedialog.askdirectory(initialdir=self.current_folder)
        if not folder:
            return

        if os.path.abspath(folder) == os.path.abspath(self.current_folder):
            folder = os.path.join(self.current_folder, "numbered")

        self.output_folder = folder
        os.makedirs(self.output_folder, exist_ok=True)
        self.update_output_folder_label()

    def set_manual_number_for_current(self):
        selection = self.listbox.curselection()
        if not selection:
            return
        idx = selection[0]

        value_str = self.manual_number_var.get().strip()
        if not value_str:
            messagebox.showwarning("Предупреждение", "Введите номер.")
            return

        try:
            value = int(value_str)
        except ValueError:
            value = None

        if value is None or value <= 0:
            messagebox.showerror("Ошибка", "Номер должен быть положительным целым числом.")
            return

        self.manual_start_numbers[idx] = value
        self.update_preview()

    def reset_manual_number_for_current(self):
        selection = self.listbox.curselection()
        if not selection:
            return
        idx = selection[0]

        if idx in self.manual_start_numbers:
            del self.manual_start_numbers[idx]

        self.manual_number_var.set("")
        self.update_preview()

    def on_toggle_skip_current(self):
        selection = self.listbox.curselection()
        if not selection:
            return
        idx = selection[0]
        if self.skip_current_var.get():
            self.per_image_skip.add(idx)
        else:
            self.per_image_skip.discard(idx)
        self.update_preview()

    def on_position_mode_changed(self, event=None):
        display = self.position_display_var.get()
        code = POSITION_MODES.get(display, "rb")
        self.position_mode_var.set(code)
        self.update_preview()

    def apply_to_all(self):
        if not self.image_paths:
            messagebox.showwarning("Предупреждение", "Нет загруженных изображений.")
            return

        self.recalculate_numbering()

        out_dir = self.output_folder or os.path.join(self.current_folder, "numbered")
        if os.path.abspath(out_dir) == os.path.abspath(self.current_folder):
            out_dir = os.path.join(self.current_folder, "numbered")
        os.makedirs(out_dir, exist_ok=True)

        total = len(self.image_paths)
        processed = 0

        for idx, path in enumerate(self.image_paths):
            number = self.index_to_number.get(idx)
            if number is None:
                continue

            try:
                with Image.open(path) as im:
                    if im.mode not in ("RGB", "RGBA"):
                        im = im.convert("RGBA")
                    else:
                        im = im.copy()

                    im = self.draw_number_on_image(idx, im, number)

                    ext = os.path.splitext(path)[1].lower()
                    if ext in (".jpg", ".jpeg") and im.mode == "RGBA":
                        im = im.convert("RGB")

                    out_path = os.path.join(out_dir, os.path.basename(path))
                    im.save(out_path)

                processed += 1
                self.status_label.config(
                    text=f"Обработка: {processed} из {len(self.index_to_number)} (файл {idx + 1}/{total})"
                )
                self.master.update_idletasks()
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось обработать файл {path}:\n{e}")

        self.status_label.config(
            text=f"Готово. Пронумеровано изображений: {processed}. Файлы сохранены в {out_dir}"
        )
        messagebox.showinfo(
            "Готово",
            f"Обработка завершена.\nПронумеровано изображений: {processed}.\n"
            f"Результаты сохранены в папке:\n{out_dir}",
        )


def main():
    root = tk.Tk()
    app = ImageNumberingApp(root)

    # Попробуем развернуть окно на максимум там, где это возможно
    try:
        root.state("zoomed")
    except tk.TclError:
        try:
            root.attributes("-zoomed", True)
        except tk.TclError:
            pass

    root.mainloop()


if __name__ == "__main__":
    main()
