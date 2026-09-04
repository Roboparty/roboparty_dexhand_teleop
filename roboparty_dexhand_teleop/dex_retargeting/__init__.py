__version__ = "0.4.7"


def __getattr__(name):
    if name == "RetargetingConfig":
        from .retargeting_config import RetargetingConfig

        return RetargetingConfig
    raise AttributeError(name)
