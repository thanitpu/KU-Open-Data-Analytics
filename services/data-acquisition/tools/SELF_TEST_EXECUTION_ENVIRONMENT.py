from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))

from control_plane.execution_environment import qualification

source={'source_id':'SRC-003','url':'https://gourmetmarketthailand.com/','name':'Gourmet Market'}
cloud=qualification(source,'cloud-hosted')
assert cloud['allowed'] is False
assert cloud['preferred_live_environment']=='edge'
assert cloud['cloud_hosted_status']=='blocked'
edge=qualification(source,'edge')
assert edge['allowed'] is True
local=qualification(source,'local')
assert local['allowed'] is True
other=qualification({'url':'https://example.com/'},'cloud-hosted')
assert other['allowed'] is True
print('Execution environment qualification: PASS')
