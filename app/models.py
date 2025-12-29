from sqlmodel import SQLModel, Field
from datetime import datetime

class TaskModel(SQLModel, table=True):
    __tablename__ = "tasks"
    id: int | None = Field(primary_key=True)
    title: str
    description: str
    done: bool = False

class ProductModel(SQLModel, table=True):
    __tablename__ = "products"
    id: int | None = Field(primary_key=True)
    name: str
    price: str
    link: str
    discount: float = 0.0  # Добавьте поле для скидки
    created_at: datetime = Field(default_factory=lambda: datetime.now())