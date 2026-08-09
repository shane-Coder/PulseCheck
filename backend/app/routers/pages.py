from fastapi import APIRouter, Depends, Request

from app.deps import get_current_user_optional
from app.templating import templates

router = APIRouter(tags=["pages"])


@router.get("/docs")
def docs(request: Request, user=Depends(get_current_user_optional)):
    return templates.TemplateResponse("docs.html", {"request": request, "user": user})
