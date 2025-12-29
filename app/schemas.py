from pydantic import BaseModel

class TaskCreate(BaseModel):
    title: str
    description: str

class TaskUpdate(TaskCreate):
    title: str
    description: str
    done: bool = False

class Task(TaskUpdate):
    id: int

class Product(BaseModel):
    name: str
    price: str
    link: str
    discount: float = 0.0