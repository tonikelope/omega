# -*- coding: utf-8 -*-

"""
  ___  __  __ _____ ____    _    
 / _ \|  \/  | ____/ ___|  / \   
| | | | |\/| |  _|| |  _  / _ \  
| |_| | |  | | |__| |_| |/ ___ \ 
 \___/|_|  |_|_____\____/_/   \_\

 _              _ _        _                  
| |_ ___  _ __ (_) | _____| | ___  _ __   ___ 
| __/ _ \| '_ \| | |/ / _ \ |/ _ \| '_ \ / _ \
| || (_) | | | | |   <  __/ | (_) | |_) |  __/
 \__\___/|_| |_|_|_|\_\___|_|\___/| .__/ \___|
                                  |_|         
                                 
HACK -> https://github.com/alfa-addon/addon/issues/1285#issuecomment-1850966175

"""

import sys

original_path = sys.path
fixed_path = [path for path in original_path if not path.endswith("packages")]


def fix_path():
    if sys.version_info[0] >= 3:
        sys.path = fixed_path


def unfix_path():
    sys.path = original_path
