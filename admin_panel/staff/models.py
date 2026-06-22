from django.db import models


class Store(models.Model):
    phone = models.BigIntegerField(verbose_name='Номер телефона')
    name = models.CharField(verbose_name='Имя сотрудника', max_length=50)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = 'Магазин'
        verbose_name_plural = 'Магазины'


class Staff(models.Model):
    HELP_TEXT = 'Нужно для авторизации сотрудников, чтобы отслеживать их премию'
    ROLES = [
        ('ai_creator', 'Специалист по генерации контента'),
        ('searchman', 'Специалист по поиску товаров'),
    ]

    phone = models.BigIntegerField(verbose_name='Номер телефона', help_text=HELP_TEXT)
    name = models.CharField(verbose_name='Имя сотрудника', max_length=50)
    role = models.CharField(verbose_name='Роль', choices=ROLES, max_length=50)

    age = models.IntegerField(verbose_name='Возраст (Необязательно)', null=True, blank=True)
    tg_id = models.BigIntegerField(verbose_name='Telegram ID', help_text=HELP_TEXT, null=True, blank=True)
    registred = models.BooleanField(verbose_name='Уже вошли в бота?', default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = 'Сотрудник'
        verbose_name_plural = 'Сотрудники'


class Image(models.Model):
    image = models.ImageField(verbose_name='Изображение', upload_to='images/')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.image.name
    
    class Meta:
        verbose_name = 'Изображение'
        verbose_name_plural = 'Изображения'


class Product(models.Model):
    creator = models.ForeignKey(
        Staff,
        verbose_name='Поисковик',
        on_delete=models.CASCADE
    )
    store = models.ForeignKey(
        Store,
        verbose_name='Магазин',
        on_delete=models.CASCADE
    )

    main_image = models.OneToOneField(
        Image,
        on_delete=models.CASCADE,
        verbose_name='Главная фотка товара',
        related_name='main_image'
    )
    images = models.ManyToManyField(
        Image,
        verbose_name='Фотки товара',
        related_name='products',
        blank=True,
    )

    name = models.CharField(max_length=100, verbose_name='Название товара')
    size = models.CharField(max_length=100, verbose_name='Размеры')
    color = models.CharField(max_length=100, verbose_name='Цвета')
    material = models.CharField(max_length=100, verbose_name='Материал')
    characteristics = models.CharField(max_length=100, verbose_name='Характеристики')
    packaging = models.CharField(max_length=100, verbose_name='Комплектация')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = 'Товар от поисковика'
        verbose_name_plural = 'Товары от поисковика'


class AiImage(models.Model):
    creator = models.ForeignKey(
        Staff,
        verbose_name='Создатель ии-изображения',
        on_delete=models.CASCADE
    )
    product = models.ForeignKey(
        Product,
        verbose_name='Продукт ии-изображения',
        on_delete=models.CASCADE
    )
    image = models.ImageField(verbose_name='Изображение', upload_to='ai_images/')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.image.name
    
    class Meta:
        verbose_name = 'ИИ-Изображение'
        verbose_name_plural = 'ИИ-Изображения'