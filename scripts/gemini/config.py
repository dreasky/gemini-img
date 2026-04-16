"""Gemini configuration constants."""

GEMINI_URL = "https://gemini.google.com/app"
QUALITY_SUFFIX = ", ultra sharp, high definition, crystal clear details"

# Selectors - Updated based on actual HTML structure
CHAT_INPUT_SELECTOR = '.ql-editor[contenteditable="true"]'
IMAGE_READY_SELECTOR = 'button[data-test-id="download-generated-image-button"]'
IMAGE_ELEMENT_SELECTOR = "button.image-button img.image"
MORE_MENU_SELECTOR = 'button[data-test-id="more-menu-button"]'
DOWNLOAD_BTN_SELECTOR = 'button[data-test-id="image-download-button"]'

# Tools button - toolbox drawer button with "工具" text
TOOLS_BTN_SEL = '.toolbox-drawer-button, button:has-text("工具"), button[aria-haspopup="menu"]'

# Make image button - in the dropdown menu
MAKE_IMAGE_CHIP_SEL = '.toolbox-drawer-item-list-button:has-text("制作图片"), button:has-text("制作图片")'
