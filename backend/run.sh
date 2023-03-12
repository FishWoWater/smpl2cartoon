#!/bin/bash

export SMPLCARTOON_PORT=5905
gunicorn -w 4 -b 0.0.0.0:$SMPLCARTOON_PORT app:app -t 600
