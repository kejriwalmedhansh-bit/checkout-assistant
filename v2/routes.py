"""
v2/routes.py — server-rendered (Jinja-only) product explorer, mounted under /v2.

Three-step flow, all via plain form POSTs (no JS):
  GET  /v2          -> search bar
  POST /v2/search   -> google_shopping, dropdown of products
  POST /v2/product  -> google_product, full detail page
"""

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from v2 import searchapi

router = APIRouter(prefix="/v2")
templates = Jinja2Templates(directory="templates/v2")


@router.get("", response_class=HTMLResponse)
async def v2_home(request: Request):
    return templates.TemplateResponse(request, "search.html")


@router.post("/search", response_class=HTMLResponse)
async def v2_search(request: Request, query: str = Form("")):
    query = query.strip()
    data = searchapi.search_products(query)
    products = [
        p for p in data.get("shopping_results", []) if p.get("product_token")
    ]
    return templates.TemplateResponse(
        request,
        "products.html",
        {"query": query, "products": products, "error": data.get("error")},
    )


@router.post("/product", response_class=HTMLResponse)
async def v2_product(request: Request, product_token: str = Form("")):
    data = searchapi.get_product(product_token)
    return templates.TemplateResponse(
        request,
        "product.html",
        {
            "error": data.get("error"),
            "product": data.get("product"),
            "offers": data.get("offers", []),
            "typical_prices": data.get("typical_prices"),
            "specifications": data.get("specifications", []),
            "related_products": data.get("related_products", []),
            "review_results": data.get("review_results"),
        },
    )
