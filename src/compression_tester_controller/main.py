from protocols import run_trial

CONN_STR = 'postgresql://domanlab:dn757657@192.168.137.199:5432/compression_testing'


if __name__ == '__main__':
    run_trial(
        trial_id=1,
        cam_settings_id=1,
        db_conn=CONN_STR,
        server_ip='192.167.137.199'
    )
