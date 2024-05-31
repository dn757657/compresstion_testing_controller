import logging
import uuid

logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)

# from acquisition_protocols import run_trial, add_default_camera_params , run_force_trial
from post_protocols import process_trial, determine_plane_colors, add_reconstruction_defaults

from compression_testing_data.models.samples import Phantom, Sample, Print
from compression_testing_data.models.testing import CompressionTrial, CompressionStep, ProcessedSTL, ProcessedPointCloud
from compression_testing_data.meta import get_session

CONN_STR = 'postgresql://domanlab:dn757657@192.168.1.3:5432/compression_testing'

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
        frames_per_step_target=0,
        strain_delta_target=0.01,
        strain_limit=0.8,
        force_limit=1000,
        force_unit='N',
        # phantom_id=6
        sample_id=57
    )

    session.add(new_trial)
    session.commit()
    logging.info(f"New Trial created @ ID: {new_trial.id}")
    session.close
    pass


# def vol_test():
#     server_ip = '192.168.1.2'
#     source_base_path=f'\\\{server_ip}\\Public\\postgres_data'
#     # source_base_path=f'C:\\Users\\Daniel\\default_unused\\Desktop'
#     stl_name2 = 'a01292f8-22da-4617-bbf7-1e486119cc1b_watertight.stl'
#     stl_name = 'a01292f8-22da-4617-bbf7-1e486119cc1b.stl'
#     stl_name_out = 'a01292f8-22da-4617-bbf7-1e486119cc1b_out.stl'

#     # stl_name = 'bcf7e87a-52db-4d31-9312-e7916999b0e0.stl'

#     Session = get_session(conn_str=CONN_STR)
#     session = Session()

#     stl = session.query(ProcessedSTL).filter(ProcessedSTL.file_name == stl_name).first()
#     step_id = stl.compression_step_id
#     step = session.query(CompressionStep).filter(CompressionStep.id == step_id).first()
#     processed_ply = session.query(ProcessedPointCloud).filter(ProcessedPointCloud.id == stl.processed_point_cloud_id).first()
#     scale_factor = processed_ply.scaling_factor
#     step = session.query(CompressionStep).filter(CompressionStep.id == step_id).first()
#     trial_id = step.compression_trial_id
#     trial = session.query(CompressionTrial).filter(CompressionTrial.id == trial_id).first()
#     trial_name = trial.name

#     stl_path = f"{source_base_path}\\{trial_name}\\{stl_name}"
#     # stl_path = f"{source_base_path}\\{stl_name2}"
#     vol_raw = get_stl_volume(scaling_factor=scale_factor, stl_path=stl_path)

#     stl_path_out = f"{source_base_path}\\{trial_name}\\{stl_name_out}"
#     pymeshfix.clean_from_file(stl_path, stl_path_out)
#     vol_tight = get_stl_volume(scaling_factor=scale_factor, stl_path=stl_path_out)

#     # your_mesh = mesh.Mesh.from_file(stl_path)
#     # volume_new, cog, inertia = your_mesh.get_mass_properties()
#     # volume_new = volume_new * (scale_factor ** 3)
    
#     return
import pandas as pd
def trial_ids_by_testset(test_set_ids, session):

    query = session.query(CompressionTrial).filter(CompressionTrial.test_set_id.in_(test_set_ids))
    df = pd.read_sql(sql=query.statement, con=session.bind)
    
    trial_ids = df['id'].unique()
    trial_ids = [int(x) for x in trial_ids]

    return trial_ids


if __name__ == '__main__':
    Session = get_session(conn_str=CONN_STR)
    session = Session()
    # create_phantom()
    # for i in range(0, 10):
    create_trial()
    # add_reconstruction_defaults(session=session)
    # add_default_camera_params(session=session)
    
    # run_force_trial(
    #     trial_id=151,
    #     db_conn=CONN_STR,
    # )

    # run_trial(
    #     trial_id=150,
    #     cam_settings_id=1,
    #     db_conn=CONN_STR,
    #     server_ip='192.168.1.3'
    # )

    # vol_test()

    # from post_protocols import get_calibration_constant
    # get_calibration_constant(db_conn=CONN_STR, phantom_ids=[1, 5, 6])

    # while True:
    #     server_ip = '192.168.1.3'
    #     trial_ids = trial_ids_by_testset(test_set_ids=['aa36a5ab-cd07-4b3b-962b-c5d9b1b3105f'], session=session)
    #     trial_ids = trial_ids_by_testset(test_set_ids=['6b6e87d5-0c91-4f4a-b41a-2098a543927b'], session=session)
    #     trial_ids = trial_ids_by_testset(test_set_ids=['63d75ec4-c367-4e4a-8902-998b58ddb051'], session=session)
    #     trial_ids = sorted(trial_ids, reverse=False)
    #     # trial_ids = [35]
    #     for trial_id in trial_ids:
    #         # if trial_id not in [130, 93, 56, 47, 98]:
    #         process_trial(
    #             trial_id=trial_id,
    #             metashape_ply_generation_settings_id=1,
    #             metashape_ply_export_settings_id=1,
    #             metashape_stl_generation_settings_id=1,
    #             o3d_plane_segmentaion_settings_id=5,
    #             o3d_dbscan_clustering_settings_id=6,
    #             platon_side_color_setting_id=4,
    #             platon_face_color_setting_id=3,
    #             platon_dims_id=2,
    #             stl_scaling_factor_id=1,
    #             db_conn=CONN_STR,
    #             source_base_path=f'\\\{server_ip}\\Public\\postgres_data',
    #             make_full_ply=True,
    #             make_processed_ply=True,
    #             make_raw_stl=True, 
    #             make_processed_stl=True
    #         )

    # determine_plane_colors(
    #     step_id=13,
    #     metashape_ply_generation_settings_id=1,
    #     metashape_ply_export_settings_id=1,
    #     o3d_plane_segmentaion_settings_id=1,
    #     db_conn=CONN_STR,
    #     source_base_path=f'\\\{server_ip}\\Public\\postgres_data',
    # )