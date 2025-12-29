from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import select, func
from app.database import get_db, DBSession
from app.models import ProductModel
from app.schemas import Product

router = APIRouter(prefix="/products", tags=["products"])

@router.get("", response_model=list[Product])
async def get_products(
    limit: int = 100,
    offset: int = 0,
    db: DBSession = Depends(get_db)
):
    """Получить список товаров"""
    stmt = select(ProductModel).offset(offset).limit(limit)
    res = await db.execute(stmt)
    products = res.scalars().all()
    return products

@router.get("/stats")
async def get_products_stats(db: DBSession = Depends(get_db)):
    """Получить статистику по товарам"""
    stmt = select(func.count(ProductModel.id))
    result = await db.execute(stmt)
    total = result.scalar() or 0
    
    if total == 0:
        return {
            "total": 0,
            "last_update": None,
            "last_product": None
        }
    
    # Последний товар
    stmt_last = select(ProductModel).order_by(ProductModel.created_at.desc()).limit(1)
    result_last = await db.execute(stmt_last)
    last_product = result_last.scalar_one_or_none()
    
    return {
        "total": total,
        "last_update": last_product.created_at.isoformat() if last_product else None,
        "last_product": {
            "name": last_product.name if last_product else None,
            "price": last_product.price if last_product else None,
            "link": last_product.link if last_product else None
        } if last_product else None
    }

@router.get("/last")
async def get_last_products(
    limit: int = 5,
    db: DBSession = Depends(get_db)
):
    """Получить последние товары"""
    stmt = select(ProductModel).order_by(ProductModel.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    products = result.scalars().all()
    return products

@router.get("/top-discount")
async def get_top_products_with_discount(
    limit: int = 10,
    db: DBSession = Depends(get_db)
):
    """Получить топ товаров с наибольшей скидкой"""
    stmt = select(ProductModel).order_by(ProductModel.discount.desc()).limit(limit)
    result = await db.execute(stmt)
    products = result.scalars().all()
    return products

@router.get("/{product_id}", response_model=Product)
async def get_product(product_id: int, db: DBSession = Depends(get_db)):
    """Получить товар по ID"""
    product = await db.get(ProductModel, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product