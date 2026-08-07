from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates

from app.deps import get_current_user_optional

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/docs")
def docs(request: Request, user=Depends(get_current_user_optional)):
    return templates.TemplateResponse("docs.html", {"request": request, "user": user})
