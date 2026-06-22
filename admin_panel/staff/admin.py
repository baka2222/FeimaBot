import re

from django.contrib import admin
from django.db.models import Count
from django.http import HttpResponse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill, Border, Side

from .models import AiImage, Image, Product, Staff, Store


def _strip_html(value: str) -> str:
    return re.sub(r'<[^>]+>', '', str(value))


def _img(url: str, size: int = 50) -> str:
    """Картинка с кликом — открывает оригинал в новой вкладке."""
    return (
        f'<a href="{url}" target="_blank" title="Открыть полный размер">'
        f'<img src="{url}" width="{size}" height="{size}" '
        f'style="object-fit:cover;border-radius:5px;margin:1px;'
        f'cursor:zoom-in;transition:opacity .15s;" '
        f'onmouseover="this.style.opacity=\'0.8\'" '
        f'onmouseout="this.style.opacity=\'1\'" />'
        f'</a>'
    )


def _safe_img(field, size: int = 50):
    if not field:
        return '—'
    try:
        return mark_safe(_img(field.url, size))
    except (ValueError, AttributeError):
        return 'Файл не найден'

def export_to_excel(modeladmin, request, queryset):
    opts = modeladmin.model._meta
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = (
        f'attachment; filename={opts.verbose_name_plural}.xlsx'
    )
    wb = Workbook()
    ws = wb.active
    ws.title = str(opts.verbose_name_plural)

    display_fields = modeladmin.get_list_display(request)
    headers = []
    for field in display_fields:
        method = getattr(modeladmin, field, None) if isinstance(field, str) else field
        label = getattr(method, 'short_description', None) or (
            opts.get_field(field).verbose_name if isinstance(field, str) else field
        )
        headers.append(str(label))
    ws.append(headers)

    header_fill = PatternFill('solid', fgColor='2E86AB')
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center', vertical='center')

    for obj in queryset:
        row = []
        for field in display_fields:
            if callable(field):
                value = field(obj)
            elif hasattr(modeladmin, field):
                value = getattr(modeladmin, field)(obj)
            else:
                value = getattr(obj, field, '')
            row.append(_strip_html(value) if value is not None else '')
        ws.append(row)

    for col in ws.columns:
        max_len = max((len(str(cell.value or '')) for cell in col), default=10)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 50)

    wb.save(response)
    return response

export_to_excel.short_description = 'Экспортировать в Excel'

BONUS_PER_NORM = 300 
NORM_SIZE      = 30   

def export_bonuses(modeladmin, request, queryset):  
    """Отчёт по премиям: по каждому поисковику — разбивка по магазинам."""
    searchmen = queryset.filter(role='searchman')

    rows = (
        Product.objects
        .filter(creator__in=searchmen)
        .values(
            'creator__id', 'creator__name', 'creator__phone',
            'store__name',
        )
        .annotate(cnt=Count('id'))
        .order_by('creator__name', 'store__name')
    )

    wb = Workbook()
    ws = wb.active
    ws.title = 'Премии'

    # ── Стили ──
    blue_fill   = PatternFill('solid', fgColor='2E86AB')
    green_fill  = PatternFill('solid', fgColor='A8D5BA')
    yellow_fill = PatternFill('solid', fgColor='FFE066')
    gray_fill   = PatternFill('solid', fgColor='D9D9D9')
    thin = Side(style='thin', color='AAAAAA')
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    def _style(cell, fill=None, bold=False, align='left', color='000000'):
        cell.font = Font(bold=bold, color=color)
        cell.alignment = Alignment(horizontal=align, vertical='center', wrap_text=True)
        cell.border = border
        if fill:
            cell.fill = fill

    headers = ['Сотрудник', 'Телефон', 'Магазин',
               'Загружено товаров', f'Норм (×{NORM_SIZE})', f'Премия (сом)']
    ws.append(headers)
    ws.row_dimensions[1].height = 22
    for col_idx, _ in enumerate(headers, 1):
        _style(ws.cell(1, col_idx), fill=blue_fill, bold=True, align='center', color='FFFFFF')

    ws.column_dimensions['A'].width = 20
    ws.column_dimensions['B'].width = 16
    ws.column_dimensions['C'].width = 25
    ws.column_dimensions['D'].width = 20
    ws.column_dimensions['E'].width = 16
    ws.column_dimensions['F'].width = 16

    current_staff_id = None
    staff_bonus = 0
    grand_total = 0
    data_rows = list(rows)

    def _flush_staff_total(row_num, name, bonus):
        ws.append(['', '', f'Итого — {name}', '', '', bonus])
        r = ws.max_row
        for c in range(1, 7):
            _style(ws.cell(r, c), fill=green_fill, bold=True, align='right' if c == 6 else 'left')
        ws.cell(r, 6).number_format = '#,##0'

    for i, row in enumerate(data_rows):
        sid    = row['creator__id']
        name   = row['creator__name']
        phone  = str(row['creator__phone'])
        store  = row['store__name']
        cnt    = row['cnt']
        norms  = cnt // NORM_SIZE
        bonus  = norms * BONUS_PER_NORM

        if current_staff_id is not None and sid != current_staff_id:
            _flush_staff_total(ws.max_row, prev_name, staff_bonus)
            staff_bonus = 0

        current_staff_id = sid
        prev_name = name
        staff_bonus += bonus
        grand_total += bonus

        show_name  = name  if (i == 0 or data_rows[i-1]['creator__id'] != sid) else ''
        show_phone = phone if (i == 0 or data_rows[i-1]['creator__id'] != sid) else ''

        ws.append([show_name, show_phone, store, cnt, norms, bonus])
        r = ws.max_row
        row_fill = yellow_fill if bonus > 0 else None
        for c in range(1, 7):
            _style(ws.cell(r, c), fill=row_fill)
        ws.cell(r, 4).alignment = Alignment(horizontal='center')
        ws.cell(r, 5).alignment = Alignment(horizontal='center')
        ws.cell(r, 6).number_format = '#,##0'

    if current_staff_id is not None:
        _flush_staff_total(ws.max_row, prev_name, staff_bonus)

    ws.append([])
    ws.append(['', '', 'ИТОГО ПРЕМИЙ', '', '', grand_total])
    r = ws.max_row
    for c in range(1, 7):
        _style(ws.cell(r, c), fill=gray_fill, bold=True, align='right' if c == 6 else 'left')
    ws.cell(r, 6).number_format = '#,##0'

    ws.append([])
    ws.append([f'* 1 норма = {NORM_SIZE} товаров = {BONUS_PER_NORM} сом'])
    ws.append(['* Жёлтые строки — магазины с начисленной премией'])

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename=Премии.xlsx'
    wb.save(response)
    return response

export_bonuses.short_description = '💰 Экспорт премий'


class ProductImageInline(admin.TabularInline):
    """Фото товара (M2M) — просмотр и удаление отдельных фото."""
    model = Product.images.through
    extra = 0
    fields = ('preview', 'image_path')
    readonly_fields = ('preview', 'image_path')
    verbose_name = 'Фото товара'
    verbose_name_plural = 'Фото товара'
    can_add = False

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('image')

    @admin.display(description='Превью')
    def preview(self, obj):
        return _safe_img(obj.image.image if obj.image else None, 70)

    @admin.display(description='Файл')
    def image_path(self, obj):
        if not obj.image:
            return '—'
        return format_html(
            '<a href="/admin/staff/image/{}/change/" target="_blank">{}</a>',
            obj.image_id, obj.image.image.name,
        )


class ProductInlineForStore(admin.TabularInline):
    model = Product
    fk_name = 'store'
    extra = 0
    fields = ('name', 'creator', 'main_image_preview', 'images_count',
              'size', 'color', 'created_at')
    readonly_fields = ('main_image_preview', 'images_count', 'created_at')
    show_change_link = True

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'creator', 'main_image'
        ).prefetch_related('images')

    @admin.display(description='Главное фото')
    def main_image_preview(self, obj):
        return _safe_img(obj.main_image.image if obj.main_image else None, 45)

    @admin.display(description='Доп. фото')
    def images_count(self, obj):
        n = obj.images.count()
        return f'{n} шт.' if n else '—'


class ProductInlineForStaff(admin.TabularInline):
    model = Product
    fk_name = 'creator'
    extra = 0
    fields = ('name', 'store', 'main_image_preview', 'images_count', 'created_at')
    readonly_fields = ('main_image_preview', 'images_count', 'created_at')
    show_change_link = True
    can_add = False

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'store', 'main_image'
        ).prefetch_related('images')

    @admin.display(description='Главное фото')
    def main_image_preview(self, obj):
        return _safe_img(obj.main_image.image if obj.main_image else None, 45)

    @admin.display(description='Доп. фото')
    def images_count(self, obj):
        n = obj.images.count()
        return f'{n} шт.' if n else '—'


class AiImageInlineForProduct(admin.TabularInline):
    model = AiImage
    fk_name = 'product'
    extra = 0
    fields = ('preview', 'creator', 'created_at')
    readonly_fields = ('preview', 'created_at')
    show_change_link = True

    @admin.display(description='Превью')
    def preview(self, obj):
        return _safe_img(obj.image, 45)


class AiImageInlineForStaff(admin.TabularInline):
    model = AiImage
    fk_name = 'creator'
    extra = 0
    fields = ('preview', 'product', 'created_at')
    readonly_fields = ('preview', 'created_at')
    show_change_link = True
    can_add = False

    @admin.display(description='Превью')
    def preview(self, obj):
        return _safe_img(obj.image, 45)


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'product_count', 'created_at')
    list_display_links = ('name',)
    list_filter = (('created_at', admin.DateFieldListFilter),)
    search_fields = ('name', 'phone')
    inlines = [ProductInlineForStore]
    actions = [export_to_excel]
    list_per_page = 25
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        (None, {'fields': ('name', 'phone')}),
        ('Даты', {'classes': ('collapse',), 'fields': ('created_at', 'updated_at')}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_cnt=Count('product'))

    @admin.display(description='Товаров', ordering='_cnt')
    def product_count(self, obj):
        return obj._cnt


@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'role', 'registred', 'tg_id', 'created_at')
    list_display_links = ('name',)
    list_editable = ('registred',)
    list_filter = ('role', 'registred', ('created_at', admin.DateFieldListFilter))
    search_fields = ('name', 'phone', 'tg_id')
    inlines = [ProductInlineForStaff, AiImageInlineForStaff]
    actions = [export_to_excel, export_bonuses]
    list_per_page = 25
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        (None, {'fields': ('name', 'phone', 'role')}),
        ('Дополнительно', {
            'classes': ('collapse',),
            'fields': ('age', 'tg_id', 'registred'),
        }),
        ('Даты', {'classes': ('collapse',), 'fields': ('created_at', 'updated_at')}),
    )


@admin.register(Image)
class ImageAdmin(admin.ModelAdmin):
    list_display = ('preview', 'image', 'created_at')
    list_display_links = ('preview', 'image')
    list_filter = (('created_at', admin.DateFieldListFilter),)
    search_fields = ('image',)
    readonly_fields = ('preview', 'created_at', 'updated_at')
    actions = [export_to_excel]
    list_per_page = 30

    fieldsets = (
        (None, {'fields': ('image', 'preview')}),
        ('Даты', {'classes': ('collapse',), 'fields': ('created_at', 'updated_at')}),
    )

    @admin.display(description='Превью')
    def preview(self, obj):
        return _safe_img(obj.image, 80)


@admin.register(AiImage)
class AiImageAdmin(admin.ModelAdmin):
    list_display = ('preview', 'creator_link', 'product_link', 'created_at')
    list_display_links = ('preview',)
    list_filter = ('creator', 'product', ('created_at', admin.DateFieldListFilter))
    search_fields = ('creator__name', 'creator__phone', 'product__name')
    readonly_fields = ('preview', 'created_at', 'updated_at')
    raw_id_fields = ('creator', 'product')
    actions = [export_to_excel]
    list_per_page = 25
    date_hierarchy = 'created_at'

    fieldsets = (
        (None, {'fields': ('creator', 'product', 'image', 'preview')}),
        ('Даты', {'classes': ('collapse',), 'fields': ('created_at', 'updated_at')}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('creator', 'product')

    @admin.display(description='Превью')
    def preview(self, obj):
        return _safe_img(obj.image, 80)

    @admin.display(description='Создатель')
    def creator_link(self, obj):
        return format_html(
            '<a href="/admin/staff/staff/{}/change/">{}</a>',
            obj.creator_id, obj.creator.name,
        )

    @admin.display(description='Товар')
    def product_link(self, obj):
        return format_html(
            '<a href="/admin/staff/product/{}/change/">{}</a>',
            obj.product_id, obj.product.name,
        )


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'store_link', 'creator_link',
        'main_image_preview', 'images_count', 'created_at',
    )
    list_display_links = ('name',)
    list_filter = ('store', 'creator', ('created_at', admin.DateFieldListFilter))
    search_fields = ('name', 'store__name', 'creator__name', 'characteristics')
    readonly_fields = ('main_image_preview', 'images_gallery', 'created_at', 'updated_at')
    inlines = [ProductImageInline, AiImageInlineForProduct]
    actions = [export_to_excel]
    save_on_top = True
    list_per_page = 25
    date_hierarchy = 'created_at'
    raw_id_fields = ('store', 'creator', 'main_image')

    fieldsets = (
        ('Основное', {'fields': ('name', 'store', 'creator')}),
        ('Изображения', {
            'fields': ('main_image', 'main_image_preview', 'images_gallery'),
            'description': 'Доп. фото управляются ниже через секцию «Фото товара».',
        }),
        ('Характеристики', {
            'fields': ('size', 'color', 'material', 'characteristics', 'packaging'),
        }),
        ('Даты', {'classes': ('collapse',), 'fields': ('created_at', 'updated_at')}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'store', 'creator', 'main_image',
        ).prefetch_related('images')

    @admin.display(description='Магазин')
    def store_link(self, obj):
        return format_html(
            '<a href="/admin/staff/store/{}/change/">{}</a>',
            obj.store_id, obj.store.name,
        )

    @admin.display(description='Поисковик')
    def creator_link(self, obj):
        return format_html(
            '<a href="/admin/staff/staff/{}/change/">{}</a>',
            obj.creator_id, obj.creator.name,
        )

    @admin.display(description='Главное фото')
    def main_image_preview(self, obj):
        return _safe_img(obj.main_image.image if obj.main_image else None, 60)

    @admin.display(description='Доп. фото')
    def images_count(self, obj):
        n = obj.images.count()
        return f'{n} шт.' if n else '—'

    @admin.display(description='Галерея фото товара')
    def images_gallery(self, obj):
        parts = []
        for img in obj.images.all():
            try:
                parts.append(_img(img.image.url, 90))
            except (ValueError, AttributeError):
                pass
        return mark_safe(''.join(parts)) if parts else '—'
