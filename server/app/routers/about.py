"""The dashboard's About box: the version and where to read the user guide, privacy statement,
security policy and licences. The addresses live here so the dashboard holds no web addresses."""

from fastapi import APIRouter

from app import __version__

router = APIRouter(tags=["about"], include_in_schema=False)

REPO = "https://github.com/Redsuperninja/budget-buddy"
LINKS = [
    {"label": "User guide", "url": f"{REPO}/blob/main/docs/guide/README.md"},
    {"label": "Privacy statement", "url": f"{REPO}/blob/main/docs/PRIVACY.md"},
    {"label": "Security policy", "url": f"{REPO}/blob/main/SECURITY.md"},
    {"label": "Budget Buddy licence", "url": f"{REPO}/blob/main/LICENSE"},
    {
        "label": "Licences of the libraries it uses",
        "url": f"{REPO}/blob/main/THIRD-PARTY-NOTICES.txt",
    },
]


@router.get("/api/local/about")
def about() -> dict:
    return {"version": __version__, "links": LINKS}
