import logging
import asyncclick as click


class LogFormatter(logging.Formatter):
    # Define icons for each logging level
    icons = {
        logging.DEBUG: "🔍",
        logging.INFO: "",
        logging.WARNING: "⚠️",
        logging.ERROR: "⚠️",
        logging.CRITICAL: "🚨"
    }

    def format(self, record):
        # Prepend the appropriate icon based on log level
        icon = self.icons.get(record.levelno, "")
        record.msg = f"{icon} {record.msg}"

        if record.levelno == logging.DEBUG:
            record.msg = click.style(f'{record.msg}', fg='yellow')

        if record.levelno > logging.INFO:
            record.msg = click.style(f'{record.msg}', fg='red')
        return super().format(record)


def setup_logging(log_level=logging.INFO):
    log_format = click.style("%(asctime)s.%(msecs)03d", fg=(80, 80, 80)) + " %(message)s"
    formatter = LogFormatter(log_format, datefmt="%Y-%m-%d %H:%M:%S")

    # Configure logging
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    logging.basicConfig(
        level=log_level,
        handlers=[handler]
    )
