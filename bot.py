import logging
import importlib
from database import init_db
from telegram import BotCommand
from telegram.ext import Application

from config import BOT_TOKEN, BOT_NAME, SET_COMMANDS


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger("solurix")


# ============================================================
# TELEGRAM COMMAND MENU
# ============================================================

COMMANDS = [
    BotCommand("start", "Start Solurix"),
    BotCommand("help", "Show all commands"),
    BotCommand("profile", "View your profile"),
    BotCommand("stats", "View your statistics"),
    BotCommand("rank", "View group ranking"),
    BotCommand("daily", "Claim your daily reward"),
    BotCommand("battle", "Start a battle"),
    BotCommand("hunt", "Go on a hunt"),
    BotCommand("train", "Train your character"),
    BotCommand("explore", "Explore the world"),
    BotCommand("coins", "Check your coins"),
    BotCommand("level", "Check your level"),
]


# ============================================================
# PLUGIN LIST
# ============================================================

PLUGIN_NAMES = [
    "start",
    "help",
    "game",
    "profile",
    "ranking",
    "daily",
    "battle",
    "hunt",
    "admin",
    "auto_reply",
]


# ============================================================
# COMMAND SETUP
# ============================================================

async def setup_commands(application: Application) -> None:
    """Register Telegram command suggestions."""

    if not SET_COMMANDS:
        logger.info("Telegram command menu setup is disabled.")
        return

    await application.bot.set_my_commands(COMMANDS)

    logger.info("Command menu configured for %s.", BOT_NAME)


# ============================================================
# PLUGIN LOADER
# ============================================================

def load_plugins(application: Application) -> None:
    """Import plugins and register their handlers."""

    for plugin_name in PLUGIN_NAMES:
        try:
            module = importlib.import_module(
                f"plugins.{plugin_name}"
            )

            setup = getattr(module, "setup", None)

            if not callable(setup):
                logger.warning(
                    "Plugin %s has no callable setup() function.",
                    plugin_name,
                )
                continue

            setup(application)

            logger.info("Loaded plugin: %s", plugin_name)

        except ModuleNotFoundError as error:
            # Skip a missing plugin, but don't hide its dependencies.
            if error.name == f"plugins.{plugin_name}":
                logger.warning("Plugin not found: %s", plugin_name)
            else:
                logger.exception(
                    "Missing dependency while loading plugin: %s",
                    plugin_name,
                )
                raise

        except Exception:
            logger.exception(
                "Failed to load plugin: %s",
                plugin_name,
            )
            raise


# ============================================================
# MAIN
# ============================================================

# ============================================================
# MAIN
# ============================================================

def main() -> None:
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN is missing from config.py")

    logger.info("Starting %s...", BOT_NAME)

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(setup_commands)
        .build()
    )

    load_plugins(application)

    logger.info("All available plugins loaded. Starting polling...")

    init_db()
    application.run_polling()


if __name__ == "__main__":
    main()