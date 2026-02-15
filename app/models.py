from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.database import Base


class Admin(Base):
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Brand(Base):
    __tablename__ = "brands"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True)
    name_ar = Column(String(255), nullable=False)
    processor_key = Column(String(100), nullable=False, unique=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    store_mappings = relationship("StoreMapping", back_populates="brand", cascade="all, delete-orphan")
    sku_rules = relationship("SkuRule", back_populates="brand", cascade="all, delete-orphan")


class StoreMapping(Base):
    __tablename__ = "store_mappings"

    id = Column(Integer, primary_key=True, index=True)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=False)
    crm_store_name = Column(String(255), nullable=False)
    external_postgres_id = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    brand = relationship("Brand", back_populates="store_mappings")


class SkuRule(Base):
    __tablename__ = "sku_rules"

    id = Column(Integer, primary_key=True, index=True)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=False)
    sku_pattern = Column(String(255), nullable=False)
    target_field = Column(String(255), nullable=False)
    multiplier = Column(Integer, default=1)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    brand = relationship("Brand", back_populates="sku_rules")
