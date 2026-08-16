from typing import NoReturn

from fastapi import HTTPException, status


def error_detail(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def raise_unauthorized(message: str = "Authentication is required.") -> NoReturn:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=error_detail("unauthorized", message),
        headers={"WWW-Authenticate": "Bearer"},
    )


def raise_forbidden(message: str = "You do not have permission to perform this action.") -> NoReturn:
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=error_detail("forbidden", message),
    )


def raise_not_found(message: str = "The requested record was not found.") -> NoReturn:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=error_detail("not_found", message),
    )


def raise_conflict(message: str) -> NoReturn:
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=error_detail("conflict", message),
    )


def raise_bad_request(message: str) -> NoReturn:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=error_detail("bad_request", message),
    )
