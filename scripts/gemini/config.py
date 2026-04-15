"""Selector constants and prompt quality suffix."""

IMAGE_READY_SELECTOR   = 'button[data-test-id="download-generated-image-button"]'
IMAGE_ELEMENT_SELECTOR = 'button.image-button img.image'
MORE_MENU_SELECTOR     = 'button[data-test-id="more-menu-button"]'
DOWNLOAD_BTN_SELECTOR  = 'button[data-test-id="image-download-button"]'
TOOLS_BTN_SEL          = (
    'button[aria-label*="工具"], button[aria-label*="Tools"], button[aria-label*="tool"]'
)
MAKE_IMAGE_CHIP_SEL    = (
    'button[aria-label*="制作图片"], button[aria-label*="Create image"], '
    'button[aria-label*="Generate image"]'
)

QUALITY_SUFFIX = ", ultra sharp, high definition, crystal clear details"
GEMINI_URL     = "https://gemini.google.com/app"
