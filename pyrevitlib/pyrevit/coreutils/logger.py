import logging
import sys
import os.path

from pyrevit import PYREVIT_ADDON_NAME, EXEC_PARAMS
from pyrevit import PYREVIT_VERSION_APP_DIR, PYREVIT_FILE_PREFIX_STAMPED
from pyrevit.coreutils import prepare_html_str
from pyrevit.coreutils.emoji import emojize
from pyrevit.coreutils.envvars import set_pyrevit_env_var, get_pyrevit_env_var

DEBUG_ISC_NAME = PYREVIT_ADDON_NAME + '_debugISC'
VERBOSE_ISC_NAME = PYREVIT_ADDON_NAME + '_verboseISC'

RUNTIME_LOGGING_LEVEL = logging.WARNING
RUNTIME_FILE_LOGGING_LEVEL = logging.DEBUG

LOG_REC_FORMAT = "%(levelname)s: [%(name)s] %(message)s"

LOG_REC_FORMAT_HTML = prepare_html_str('<div style="{0}">{1}</div>')
LOG_REC_FORMAT_ERROR = LOG_REC_FORMAT_HTML.format('background:#f9f2f4;color:#c7254e;padding:10;margin:10 0 10 0',
                                                  LOG_REC_FORMAT)
LOG_REC_FORMAT_WARNING = LOG_REC_FORMAT_HTML.format('background:#F7F3F2;color:#C64325;padding:10;margin:10 0 10 0',
                                                    LOG_REC_FORMAT)
LOG_REC_FORMAT_CRITICAL = LOG_REC_FORMAT_HTML.format('background:#c7254e;color:white;padding:10;margin:10 0 10 0',
                                                     LOG_REC_FORMAT)


FILE_LOG_REC_FORMAT = "%(asctime)s %(levelname)s: [%(name)s] %(message)s"
FILE_LOG_FILENAME = '{}.log'.format(PYREVIT_FILE_PREFIX_STAMPED)
FILE_LOG_FILEPATH = os.path.join(PYREVIT_VERSION_APP_DIR, FILE_LOG_FILENAME)
FILE_LOGGING_STATUS = False


if not EXEC_PARAMS.doc_mode:
    # Setting session-wide debug/verbose status so other individual scripts know about it.
    # individual scripts are run at different time and the level settings need to be set inside current host session
    # so they can be retreieved later.
    if get_pyrevit_env_var(VERBOSE_ISC_NAME):
        RUNTIME_LOGGING_LEVEL = logging.INFO

    if get_pyrevit_env_var(DEBUG_ISC_NAME):
        RUNTIME_LOGGING_LEVEL = logging.DEBUG

    # the loader assembly sets EXEC_PARAMS.forced_debug_mode to true if user Shift-clicks on the button
    # EXEC_PARAMS.forced_debug_mode will be set by the LOADER_ADDIN_COMMAND_INTERFACE_CLASS_EXT at script runtime
    if EXEC_PARAMS.forced_debug_mode:
        RUNTIME_LOGGING_LEVEL = logging.DEBUG


# custom logger methods (for module consistency and custom adjustments) ------------------------------------------------
class DispatchingFormatter:
    def __init__(self, formatters, default_formatter):
        self._formatters = formatters
        self._default_formatter = default_formatter

    def format(self, record):
        formatter = self._formatters.get(record.levelno, self._default_formatter)
        return formatter.format(record)


class LoggerWrapper(logging.Logger):
    def __init__(self, *args):
        logging.Logger.__init__(self, *args)

    def _log(self, level, msg, args, exc_info=None, extra=None):
        # any report other than logging.INFO level reports, need to cleanup < and > character to avoid html conflict
        msg_str = str(msg)
        msg_str = msg_str.encode('ascii', 'ignore')
        msg_str = msg_str.replace(os.path.sep, '/')
        msg_str = emojize(msg_str)
        if level == logging.INFO:
            msg_str = prepare_html_str(msg_str)
        logging.Logger._log(self, level, msg_str, args, exc_info=None, extra=None)

    def getEffectiveLevel(self):
        """Overrides the parent class method to check handler.level instead of self.level.
        All loggers generated by this module use the same handlers. All set level methods set handler.level instead
        of self.level. This ensures that the level set on any logger affects all the other logger modules."""
        logger = self
        while logger:
            if len(logger.handlers) > 0:
                eff_level = logging.CRITICAL
                for hndlr in logger.handlers:
                    if hndlr.level < eff_level:
                        eff_level = hndlr.level
                return eff_level
            elif logger.level:
                return logger.level
            logger = logger.parent
        return logging.NOTSET

    def _reset_logger_env_vars(self, verbose=False, debug=False):
        set_pyrevit_env_var(VERBOSE_ISC_NAME, verbose)
        set_pyrevit_env_var(DEBUG_ISC_NAME, debug)

    def set_level(self, level):
        self.handlers[0].setLevel(level)

    def set_verbose_mode(self):
        self._reset_logger_env_vars(verbose=True, debug=False)
        self.handlers[0].setLevel(logging.INFO)

    def set_debug_mode(self):
        self._reset_logger_env_vars(verbose=False, debug=True)
        self.handlers[0].setLevel(logging.DEBUG)

    def reset_level(self):
        self._reset_logger_env_vars()
        self.handlers[0].setLevel(RUNTIME_LOGGING_LEVEL)

    def get_level(self):
        return self.level

# setting up handlers and formatters -----------------------------------------------------------------------------------
stdout_hndlr = logging.StreamHandler(sys.stdout)
# e.g [_parser] DEBUG: Can not create command.
stdout_hndlr.setFormatter(DispatchingFormatter({logging.ERROR: logging.Formatter(LOG_REC_FORMAT_ERROR),
                                                logging.WARNING: logging.Formatter(LOG_REC_FORMAT_WARNING),
                                                logging.CRITICAL: logging.Formatter(LOG_REC_FORMAT_CRITICAL)},
                                               logging.Formatter(LOG_REC_FORMAT)))
stdout_hndlr.setLevel(RUNTIME_LOGGING_LEVEL)

file_hndlr = logging.FileHandler(FILE_LOG_FILEPATH, mode='a', delay=True)
file_formatter = logging.Formatter(FILE_LOG_REC_FORMAT)
file_hndlr.setFormatter(file_formatter)
file_hndlr.setLevel(RUNTIME_FILE_LOGGING_LEVEL)

# setting up public logger. this will be imported in with other modules ------------------------------------------------
logging.setLoggerClass(LoggerWrapper)


loggers = {}


def get_logger(logger_name):
    if loggers.get(logger_name):
        return loggers.get(logger_name)
    else:
        logger = logging.getLogger(logger_name)    # type: LoggerWrapper
        logger.addHandler(stdout_hndlr)
        logger.propagate = False
        if FILE_LOGGING_STATUS:
            logger.addHandler(file_hndlr)

        loggers.update(dict(logger_name=logger))
        return logger


def set_file_logging(status):
    global FILE_LOGGING_STATUS
    FILE_LOGGING_STATUS = status
