"""
VoxRelay entry point.

Wires:
  - Flask app
  - Telegram bot webhook (modules.telegram_entry)
  - Voice webhooks (modules.voice_webhooks)
  - Verify flow (modules.verify)
  - Security flow (modules.security)
  - Telegram flows (modules.flows)
  - Background sweeper for stale call state
"""

import threading
import time

from flask import Flask

# Import modules in dependency order.
#   flows registers Telegram handlers at import time.
#   verify/security register their callbacks as well.
import modules.bot_core            # noqa: F401  (creates bot + sets webhook)
import modules.flows               # noqa: F401  (registers flows handlers)
import modules.verify              # noqa: F401  (registers verify callbacks)
import modules.security            # noqa: F401  (registers security callbacks)
from modules import call_state as cs
from modules.telegram_entry import tg_bp
from modules.voice_webhooks import voice_bp
from modules.verify import verify_bp
from modules.security import security_bp

app = Flask(__name__)

# ------------------------------------------------------------
# Blueprints
# ------------------------------------------------------------
app.register_blueprint(tg_bp)
app.register_blueprint(voice_bp)
app.register_blueprint(verify_bp)
app.register_blueprint(security_bp)


# ------------------------------------------------------------
# Background sweeper for stale call state
# ------------------------------------------------------------
def _state_sweeper():
    while True:
        try:
            cs.sweep(max_age_seconds=1800)
        except Exception as e:
            print(f"[sweeper] {e}", flush=True)
        time.sleep(300)


threading.Thread(target=_state_sweeper, daemon=True).start()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)