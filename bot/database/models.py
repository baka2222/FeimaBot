from datetime import datetime
from typing import Optional, List

from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .connection import Base

# Junction table for Product.images (ManyToMany)
product_images_table = Table(
    'staff_product_images',
    Base.metadata,
    Column('product_id', BigInteger, ForeignKey('staff_product.id'), primary_key=True),
    Column('image_id', BigInteger, ForeignKey('staff_image.id'), primary_key=True),
)


class Staff(Base):
    __tablename__ = 'staff_staff'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    phone: Mapped[int] = mapped_column(BigInteger)
    name: Mapped[str] = mapped_column(String(50))
    role: Mapped[str] = mapped_column(String(50))
    age: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tg_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    registred: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    products: Mapped[List['Product']] = relationship(
        'Product', back_populates='creator', foreign_keys='Product.creator_id'
    )
    ai_images: Mapped[List['AiImage']] = relationship('AiImage', back_populates='creator')


class Store(Base):
    __tablename__ = 'staff_store'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    phone: Mapped[int] = mapped_column(BigInteger)
    name: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    products: Mapped[List['Product']] = relationship('Product', back_populates='store')


class Image(Base):
    __tablename__ = 'staff_image'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    image: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Product(Base):
    __tablename__ = 'staff_product'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    creator_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('staff_staff.id'))
    store_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('staff_store.id'))
    main_image_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('staff_image.id'), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    size: Mapped[str] = mapped_column(String(100))
    color: Mapped[str] = mapped_column(String(100))
    material: Mapped[str] = mapped_column(String(100))
    characteristics: Mapped[str] = mapped_column(String(100))
    packaging: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    creator: Mapped['Staff'] = relationship(
        'Staff', back_populates='products', foreign_keys=[creator_id]
    )
    store: Mapped['Store'] = relationship('Store', back_populates='products')
    main_image: Mapped['Image'] = relationship('Image', foreign_keys=[main_image_id])
    ai_images: Mapped[List['AiImage']] = relationship('AiImage', back_populates='product')


class AiImage(Base):
    __tablename__ = 'staff_aiimage'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    creator_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('staff_staff.id'))
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('staff_product.id'))
    image: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    creator: Mapped['Staff'] = relationship('Staff', back_populates='ai_images')
    product: Mapped['Product'] = relationship('Product', back_populates='ai_images')
