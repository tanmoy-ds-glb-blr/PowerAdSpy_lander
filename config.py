import os
from pathlib import Path
import yaml

try:
    from dotenv import load_dotenv
    _ENV_PATH = Path(__file__).resolve().parent / ".env"
    load_dotenv(dotenv_path=_ENV_PATH if _ENV_PATH.is_file() else None)
except ImportError:
    pass

_DEFAULT_YAML = str(Path(__file__).resolve().parent / "config.yaml")

class Config:
    def __init__(self, network=None, yaml_path=_DEFAULT_YAML):
        if not os.path.isfile(yaml_path):
            if os.path.isfile("config.yaml"):
                yaml_path = "config.yaml"
            else:
                raise FileNotFoundError(f"Configuration file not found at '{yaml_path}'")

        with open(yaml_path, "r", encoding="utf-8") as f:
            self._config = yaml.safe_load(f) or {}

        self.default = self._config.get("default_settings", {})
        self.networks = self._config.get("networks", {})

        # If network not passed explicitly, read from config.yaml default_settings
        if not network:
            network = self.default.get("NETWORK")

        if not network:
            raise ValueError(
                "Network not specified. Please define 'NETWORK' under default_settings in config.yaml or pass it explicitly."
            )

        self.network_name = str(network).strip().lower()

        if self.network_name not in self.networks:
            raise ValueError(f"Network '{self.network_name}' not found in config.")

        self.network_config = self.networks[self.network_name]

        # Set default settings as direct attributes
        self.instances = self.default.get("INSTANCES", 1)
        self.time_gap = self.default.get("TIME_GAP_IN_INSTANCES", 10)
        self.dev_mode = self.default.get("DEV_MODE", False)
        self.hit_get_api = self.default.get("HIT_GET_API", False)
        self.skip_ads_till = self.default.get("SKIP_ADS_TILL", 0)
        self.bright_proxies = self.default.get("BRIGHT_PROXIES", False)
        self.proxy_health_check_interval = self.default.get("PROXY_HEALTH_CHECK_INTERVAL_SECONDS", 5)
        self.proxy_health_check_timeout = self.default.get("PROXY_HEALTH_CHECK_TIMEOUT_SECONDS", 5)
        self.proxy_health_country = self.default.get("PROXY_HEALTH_COUNTRY", "us")
        self.proxy_health_stale_seconds = self.default.get("PROXY_HEALTH_STALE_SECONDS", 15)

        # self.stop_after_batches = self.default.get("STOP_CODE_AFTER_N_BATCHES", False)
        # self.n_batches = self.default.get("N_BATCHES", 1)

    # Default/global setting
    def get_default(self, key):
        return self.default.get(key)

    # Network-specific API
    def get_api(self, api_key):
        val = self.network_config.get(api_key)
        return val.strip() if isinstance(val, str) else val


    # Helper methods (optional aliases)
    def main_insert_api(self):
        return self.get_api("MAIN_INSERT_API")

    def dev_insert_api(self):
        return self.get_api("DEV_INSERT_API")

    def main_s3_api(self):
        return self.get_api("MAIN_S3_API") 

    def dev_s3_api(self):
        return self.get_api("DEV_S3_API") 

    def main_post_info_api(self):
        return self.get_api("MAIN_POST_INFO_API")

    def dev_post_info_api(self):
        return self.get_api("DEV_POST_INFO_API")

    def all_network_apis(self):
        return self.network_config

    def is_dev_mode(self):
        return self.dev_mode

    def __repr__(self):
        return f"<Config network={self.network_name}, dev_mode={self.dev_mode}>"
