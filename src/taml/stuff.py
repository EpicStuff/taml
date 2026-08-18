from beartype import BeartypeConf, beartype


beartype = beartype(conf=BeartypeConf(is_color=False, violation_type=TypeError))
