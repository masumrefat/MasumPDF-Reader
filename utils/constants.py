"""Constants used across the MasumPDF Reader app."""

APP_NAME = "MasumPDF Reader"
APP_VERSION = "1.0.2"
# GitHub repo used to check for newer versions (owner/repo).
# Change this if your repository name is different.
GITHUB_REPO = "masumrefat/MasumPDF-Reader"
APP_ORG = "MasumPDF"
APP_AUTHOR = "Chowdhury Mohammad Masum Refat"
APP_LICENSE = "MIT License"
APP_PURPOSE = "For education purpose only"
APP_TAGLINE = "One for all PDF reader for researchers"

# Zoom
DEFAULT_ZOOM = 1.0
MIN_ZOOM = 0.1
MAX_ZOOM = 6.0
ZOOM_STEP = 0.15
ZOOM_LEVELS = [0.25, 0.33, 0.5, 0.66, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0, 4.0]

# Thumbnails
THUMBNAIL_WIDTH = 150
THUMBNAIL_DPI = 50

# Rendering
# Base DPI controls how sharp pages look. Bumping this to 200 (≈2.78× the
# PDF native 72 DPI) gives crisp text on any normal monitor. We also
# multiply by the screen's device-pixel-ratio at render time, so a hi-DPI
# (Retina / 4K / scaled-Windows) display ends up around 400 DPI internally.
RENDER_DPI = 150

# Quality presets the user can pick in Settings.
# Higher = sharper but slower and more memory per cached page.
RENDER_QUALITY_PRESETS = {
    "Low (faster)":  120,
    "Normal":        180,
    "High":          240,
    "Ultra":         320,
}
DEFAULT_RENDER_QUALITY = "Normal"

# View modes
VIEW_SINGLE = "single"
VIEW_CONTINUOUS = "continuous"
VIEW_TWO_PAGE = "two_page"

# Theme system
# Appearance controls the full surface (Light/Dark). Accent controls the whole
# GUI color family: toolbar highlights, selected tabs, cards, buttons, borders,
# focus rings, progress bars, and side-rail restore buttons.
THEME_LIGHT = "light"
THEME_DARK = "dark"
THEME_SYSTEM = "light"
APPEARANCES = {
    THEME_LIGHT: "Light mode",
    THEME_DARK: "Dark mode",
}
DEFAULT_APPEARANCE = THEME_LIGHT

THEME_BLUE = "blue"
THEME_GREEN = "green"
THEME_PURPLE = "purple"
THEME_ORANGE = "orange"
THEME_ROSE = "rose"
THEME_GRAPHITE = "graphite"
COLOR_THEMES = {
    THEME_BLUE: "Ocean Blue",
    THEME_GREEN: "Research Green",
    THEME_PURPLE: "Royal Purple",
    THEME_ORANGE: "Warm Orange",
    THEME_ROSE: "Rose Pink",
    THEME_GRAPHITE: "Graphite",
}
DEFAULT_COLOR_THEME = THEME_BLUE

# History
RECENT_FILES_MAX = 12

# Annotation defaults
DEFAULT_HIGHLIGHT_COLOR = "#FFEB3B"
DEFAULT_PEN_COLOR = "#E53935"
DEFAULT_PEN_WIDTH = 2

# Filters for file dialogs
PDF_FILTER = "PDF files (*.pdf)"
IMAGE_FILTER = "Image files (*.png *.jpg *.jpeg *.bmp *.tiff)"

# Supported OCR languages (codes follow tesseract)
OCR_LANGUAGES = {
    "English": "eng",
    "Spanish": "spa",
    "French": "fra",
    "German": "deu",
    "Italian": "ita",
    "Portuguese": "por",
    "Dutch": "nld",
    "Polish": "pol",
    "Czech": "ces",
    "Romanian": "ron",
    "Hungarian": "hun",
    "Greek": "ell",
    "Turkish": "tur",
    "Swedish": "swe",
    "Norwegian": "nor",
    "Danish": "dan",
    "Finnish": "fin",
    "Russian": "rus",
    "Ukrainian": "ukr",
    "Bulgarian": "bul",
    "Serbian": "srp",
    "Japanese": "jpn",
    "Chinese (Simplified)": "chi_sim",
    "Chinese (Traditional)": "chi_tra",
    "Korean": "kor",
    "Vietnamese": "vie",
    "Thai": "tha",
    "Arabic": "ara",
    "Persian": "fas",
    "Hebrew": "heb",
    "Hindi": "hin",
    "Bengali": "ben",
    "Tamil": "tam",
    "Telugu": "tel",
    "Urdu": "urd",
    "Indonesian": "ind",
    "Malay": "msa",
    "Multiple — English + most common": "eng+spa+fra+deu+chi_sim+jpn+ara+rus",
}
