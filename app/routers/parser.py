from fastapi import APIRouter, BackgroundTasks
from app.services.parser_service import OzonParser

router = APIRouter(prefix="/parser", tags=["parser"])

@router.get("")
async def parser(background_task: BackgroundTasks):
    ozon_parser = OzonParser()
    category_url = "https://www.ozon.ru/category/nastolnye-igry-13507/"  
    background_task.add_task(ozon_parser.start, category_url)
    return {"message": "Парсер успешно запущен в фоне"}