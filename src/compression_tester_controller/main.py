import logging
import uuid

logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)

from acquisition_protocols import run_trial, add_default_camera_params 
# from post_protocols import process_trial, determine_plane_colors, add_reconstruction_defaults

from compression_testing_data.models.samples import Phantom, Sample, Print
from compression_testing_data.models.testing import CompressionTrial
from compression_testing_data.meta import get_session

CONN_STR = 'postgresql://domanlab:dn757657@192.168.137.134:5432/compression_testing'

def create_phantom():
    Session = get_session(conn_str=CONN_STR)
    session = Session()

    new_phantom = Phantom(
        name='convex_cylinder',
        volume=11591.9,
        geometry_units='mm'
    )
    session.add(new_phantom)
    session.commit()
    logging.info(f"New Phantom created @ ID: {new_phantom.id}")
    session.close
    pass

def create_sample():
    Session = get_session(conn_str=CONN_STR)
    session = Session()

    new_sample = Sample(
        geometry_units='mm',
        cell_size=0.5,
        relative_density=0.1,
        n_perimeters=1
    )
    session.add(new_sample)
    session.commit()
    logging.info(f"New Sample created @ ID: {new_sample.id}")
    session.close
    pass

def create_print():
    Session = get_session(conn_str=CONN_STR)
    session = Session()

    new_print = Print(
        name='standard_20mm_cylinder',
        filament_name='Varioshore',
        printer_model='MK3S+',
        printer_settings='0000',
        stl_file='file.file'
    )
    session.add(new_print)
    session.commit()
    logging.info(f"New Print created @ ID: {new_print.id}")
    session.close
    pass

def create_trial():
    Session = get_session(conn_str=CONN_STR)
    session = Session()

    new_trial = CompressionTrial(
        name=uuid.uuid4(),
        frames_per_step_target=100,
        strain_delta_target=0.1,
        strain_limit=0.8,
        force_limit=1000,
        force_unit='N',
        phantom_id=5
        # sample_id=1
    )

    session.add(new_trial)
    session.commit()
    logging.info(f"New Trial created @ ID: {new_trial.id}")
    session.close
    pass


if __name__ == '__main__':
    # Session = get_session(conn_str=CONN_STR)
    # session = Session()
    # create_phantom()
    # create_trial()
    # add_reconstruction_defaults(session=session)
    # add_default_camera_params(session=session)
    
    run_trial(
        trial_id=28,
        cam_settings_id=1,
        db_conn=CONN_STR,
        server_ip='192.168.137.134'
    )

    # server_ip = '192.168.137.134'
    # trials = [20, 21, 22, 23, 24, 25, 26]
    # for trial in trials:
    #     process_trial(
    #         trial_id=trial,
    #         metashape_ply_generation_settings_id=1,
    #         metashape_ply_export_settings_id=1,
    #         metashape_stl_generation_settings_id=1,
    #         o3d_plane_segmentaion_settings_id=1,
    #         o3d_dbscan_clustering_settings_id=2,
    #         platon_side_color_setting_id=4,
    #         platon_face_color_setting_id=3,
    #         platon_dims_id=2,
    #         stl_scaling_factor_id=1,
    #         db_conn=CONN_STR,
    #         source_base_path=f'\\\{server_ip}\\Public\\postgres_data',
    #     )

    # determine_plane_colors(
    #     step_id=13,
    #     metashape_ply_generation_settings_id=1,
    #     metashape_ply_export_settings_id=1,
    #     o3d_plane_segmentaion_settings_id=1,
    #     db_conn=CONN_STR,
    #     source_base_path=f'\\\{server_ip}\\Public\\postgres_data',
    # )