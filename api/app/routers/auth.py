from fastapi import APIRouter, Depends, HTTPException, Response, status
from app.auth import create_access_token, verify_password, get_current_user
from app.config import Settings, get_settings
from app.schemas.auth import LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    response: Response,
    settings: Settings = Depends(get_settings),
):
    if body.email != settings.auth_email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not settings.auth_password_hash or not verify_password(body.password, settings.auth_password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token({"sub": body.email}, settings)

    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=settings.jwt_expire_minutes * 60,
    )
    return TokenResponse(access_token=token)


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token")
    return {"message": "Logged out"}


@router.get("/me")
async def me(current_user: dict = Depends(get_current_user)):
    return current_user
