import logging
import uuid
import os
import glob

logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)

import numpy as np
from dotenv import load_dotenv
from os.path import join, dirname

from compression_testing_data.meta import get_session
from compression_testing_data.models.testing import CompressionTrial, CompressionStep, Frame, MetashapeProject, FullPointCloud, ProcessedPointCloud
from compression_testing_data.models.reconstruction_settings import MetashapePlyExportSetting, MetashapePlyGenerationSetting, Open3DDBSCANClusteringSetting, Open3DSegmentationSetting
from compression_testing_data.models.acquisition_settings import PlatonDimension

from pipelines import create_full_ply, process_full_ply

from file_management import move_trial_assets,  move_file, bash_to_windows_paths

dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)


def get_full_ply(
        session,
        step,
        source_base_path: str,
        metashape_ply_generation_settings_id: int,
        metashape_ply_export_settings_id: int,
):
    full_point_cloud = None

    metashape_ply_gen_options = session.query(MetashapePlyGenerationSetting).filter(MetashapePlyGenerationSetting.id == metashape_ply_generation_settings_id).first()
    if not metashape_ply_gen_options:
        logging.info(f"Metashape PLY Generation Setting ID: {metashape_ply_generation_settings_id} not found.")
        return full_point_cloud
    metashape_ply_gen_options = metashape_ply_gen_options.__dict__

    metashape_ply_export_options = session.query(MetashapePlyExportSetting).filter(MetashapePlyExportSetting.id == metashape_ply_export_settings_id).first()
    if not metashape_ply_export_options:
        logging.info(f"Metashape PLY Export Setting ID: {metashape_ply_export_settings_id} not found.")
        return full_point_cloud
    metashape_ply_export_options = metashape_ply_export_options.__dict__

    full_point_clouds = step.full_point_clouds
    for pcd in full_point_clouds:
        if (pcd.metashape_ply_export_setting_id == metashape_ply_export_settings_id) and (pcd.metashape_ply_generation_setting_id == metashape_ply_generation_settings_id):
            full_point_cloud = pcd 
            logging.info(f"Point Cloud Found @ ID: {full_point_cloud.id}")   
    
    frames = step.frames
    if not len(frames) > 0:
        logging.info(f"No Frames Assigned to Step ID: {step.id}")
        return full_point_cloud

    if not full_point_cloud:
        
        frame_paths = [os.path.join(source_base_path, frame.file_name).__str__() for frame in frames]

        metashape_project_ext = 'psx'
        metashape_project_name = f'{uuid.uuid4()}'
        metashape_project_filename = f'{metashape_project_name}.{metashape_project_ext}'
        metashape_project_source_filepath = f'.\\{metashape_project_filename}'
        metashape_project_dest_filepath = f'{source_base_path}\\{metashape_project_filename}'


        point_cloud_ext = 'ply'
        metashape_ply_name = f'{uuid.uuid4()}'
        metashape_ply_filename=f'{metashape_ply_name}.{point_cloud_ext}'
        metashape_ply_source_filepath=f'.\\{metashape_ply_filename}'
        metashape_ply_dest_filepath=f'{source_base_path}\\{metashape_ply_filename}'

        # for sim
        with open(metashape_project_source_filepath, 'w') as file:
            file.write("")
        
        with open(metashape_ply_source_filepath, 'w') as file:
            file.write("")

        # create_ply(
        #     frames=frame_paths,
        #     metashape_point_cloud_gen_options=metashape_point_cloud_gen_options,
        #     metashape_project_path=metashape_project_source_filepath,
        #     metashape_ply_path=metashape_ply_source_filepath,
        # )

        move_file(source=metashape_project_source_filepath, destination=metashape_project_dest_filepath)
        new_meta_proj = MetashapeProject(
            name=metashape_project_name,
            file_extension=metashape_project_ext,
            file_name=metashape_project_filename,
            compression_step_id=step.id
        )
        session.add(new_meta_proj)

        move_file(source=metashape_ply_source_filepath, destination=metashape_ply_dest_filepath)
        new_meta_ply = FullPointCloud(
            name=metashape_ply_name,
            file_extension=point_cloud_ext,
            file_name=metashape_ply_filename,
            compression_step_id=step.id,
            metashape_ply_export_setting_id=metashape_ply_export_settings_id,
            metashape_ply_generation_setting_id=metashape_ply_generation_settings_id
        )
        session.add(new_meta_ply)
        session.commit()

        full_point_clouds = step.full_point_clouds
        for pcd in full_point_clouds:
            if (pcd.metashape_ply_export_setting_id == metashape_ply_export_settings_id) and (pcd.metashape_ply_generation_setting_id == metashape_ply_generation_settings_id):
                full_point_cloud = pcd 
                logging.info(f"Point Cloud Found @ ID: {full_point_cloud.id}")  

    return full_point_cloud


def get_processed_ply(
        session,
        step,
        o3d_plane_segmentaion_settings_id: int,
        o3d_dbscan_clustering_settings_id: int,
        platon_dims_id: int,
        full_ply_filepath: str,
        source_base_path: str,
        is_calibration: bool = False
):
    processed_point_cloud = None

    o3d_plane_segmentaion_settings = session.query(Open3DSegmentationSetting).filter(Open3DSegmentationSetting.id == o3d_plane_segmentaion_settings_id).first()
    if not o3d_plane_segmentaion_settings:
        logging.info(f"Open3D Plane Segmentation Setting ID: {o3d_plane_segmentaion_settings_id} not found.")
        return processed_point_cloud
    o3d_plane_segmentaion_settings = o3d_plane_segmentaion_settings.__dict__

    o3d_dbscan_clustering_settings = session.query(Open3DDBSCANClusteringSetting).filter(Open3DDBSCANClusteringSetting.id == o3d_dbscan_clustering_settings_id).first()
    if not o3d_dbscan_clustering_settings:
        logging.info(f"Open3D Plane Segmentation Setting ID: {o3d_dbscan_clustering_settings_id} not found.")
        return processed_point_cloud
    o3d_dbscan_clustering_settings = o3d_dbscan_clustering_settings.__dict__

    platon_dimensions = session.query(PlatonDimension).filter(PlatonDimension.id == platon_dims_id).first()
    if not platon_dimensions:
        logging.info(f"Platon Dimensions Setting ID: {platon_dims_id} not found.")
        return processed_point_cloud
    platon_dimensions = platon_dimensions.__dict__

    processed_point_clouds = step.processed_point_clouds
    for pcd in processed_point_clouds:
        if (pcd.open3d_segmentation_setting_id == o3d_plane_segmentaion_settings_id) and \
           (pcd.open3d_dbscan_clustering_setting_id == o3d_dbscan_clustering_settings_id) and \
           (pcd.platon_dimension_id == platon_dims_id):
            
            processed_point_cloud = pcd 
            logging.info(f"Processed Point Cloud Found @ ID: {processed_point_cloud.id}")   

    if not processed_point_cloud:

        point_cloud_ext = 'ply'
        processed_ply_name = f'{uuid.uuid4()}'
        processed_ply_filename=f'{processed_ply_name}.{point_cloud_ext}'
        processed_ply_source_filepath=f'.\\{processed_ply_filename}'
        processed_ply_dest_filepath=f'{source_base_path}\\{processed_ply_filename}'

        if is_calibration:
            num_platons = 1
        else:
            num_platons = 2

        # for sim
        with open(processed_ply_source_filepath, 'w') as file:
            file.write("")
        scaling_factor = 5

        # scaling_factor = process_full_ply(
        #     full_ply_path=full_ply_filepath,
        #     processed_ply_path=processed_ply_source_filepath,
        #     num_platons=num_platons,
        #     o3d_plane_segmentaion_settings=o3d_plane_segmentaion_settings,
        #     o3d_dbscan_clustering_settings=o3d_dbscan_clustering_settings,
        # )        

        move_file(source=processed_ply_source_filepath, destination=processed_ply_dest_filepath)
        new_proc_ply = ProcessedPointCloud(
            name=processed_ply_name,
            file_extension=point_cloud_ext,
            file_name=processed_ply_filename,
            compression_step_id=step.id,
            scaling_factor=scaling_factor,
            open3d_segmentation_setting_id=o3d_plane_segmentaion_settings_id,
            open3d_dbscan_clustering_setting_id=o3d_dbscan_clustering_settings_id,
            platon_dimension_id=platon_dims_id,
        )
        session.add(new_proc_ply)
        session.commit()

        processed_point_clouds = step.processed_point_clouds
        for pcd in processed_point_clouds:
            if (pcd.open3d_segmentation_setting_id == o3d_plane_segmentaion_settings_id) and \
            (pcd.open3d_dbscan_clustering_setting_id == o3d_dbscan_clustering_settings_id) and \
            (pcd.platon_dimension_id == platon_dims_id):
                
                processed_point_cloud = pcd 
                logging.info(f"Processed Point Cloud Found @ ID: {processed_point_cloud.id}") 

    return processed_point_cloud


def process_trial(
        trial_id: int,
        metashape_ply_generation_settings_id: int,
        metashape_ply_export_settings_id: int,
        o3d_plane_segmentaion_settings_id: int,
        o3d_dbscan_clustering_settings_id: int,
        platon_dims_id: int,
        db_conn: str,
        source_base_path: str,
        ):
    
    Session = get_session(conn_str=db_conn)
    session = Session()
    trial = session.query(CompressionTrial).filter(CompressionTrial.id == trial_id).first()
    
    if trial:
        steps  = trial.steps
        if len(steps) > 0:
            steps = sorted(steps, key=lambda x: x.strain_target)

            for step in steps:
                frames = step.frames
                if not len(frames) > 0:  # check for frames, cant create anything without frames
                    logging.info(f"No Frames assigned to Step ID: {step.name}")
                    continue

                # check if all options exist
                
                
                # to check for assets try inserting and rely on unique conditions to reject insertion?
                # if asset exists get its filepath to use in processing
                # make sure all options are accessible

                # gen point clouds
                full_point_cloud = get_full_ply(
                    session=session,
                    step=step,
                    source_base_path=os.path.join(source_base_path, trial.name),
                    metashape_ply_generation_settings_id=metashape_ply_generation_settings_id,
                    metashape_ply_export_settings_id=metashape_ply_export_settings_id,
                )

                if full_point_cloud:
                    full_point_cloud_filepath = os.path.join(source_base_path, trial.name, full_point_cloud.file_name)

                    processed_ply = get_processed_ply(
                        session=session,
                        step=step,
                        o3d_plane_segmentaion_settings_id=o3d_plane_segmentaion_settings_id,
                        o3d_dbscan_clustering_settings_id=o3d_dbscan_clustering_settings_id,
                        source_base_path=os.path.join(source_base_path, trial.name),
                        platon_dims_id=platon_dims_id,
                        full_ply_filepath=full_point_cloud_filepath,
                        is_calibration=trial.is_calibration
                    )

                    if processed_ply:
                        processed_ply_filepath = os.path.join(source_base_path, trial.name, processed_ply.file_name)
                    
                    
                # create stls
        session.close()

    pass

from pipelines import determine_plane_colors


def determine_plane_colors(
        step_id: int,
        metashape_ply_generation_settings_id: int,
        metashape_ply_export_settings_id: int,
        o3d_plane_segmentaion_settings_id: int,
        db_conn: str,
        source_base_path: str,
        plane_limit: int = 10
        ):
    
    Session = get_session(conn_str=db_conn)
    session = Session()

    step = session.query(CompressionStep).filter(CompressionStep.id == step_id).first()
    trial = session.query(CompressionTrial).filter(CompressionTrial.id == step.compression_trial_id).first()
    if step:
        frames = step.frames
        if not len(frames) > 0:  # check for frames, cant create anything without frames
            logging.info(f"No Frames assigned to Step ID: {step.name}")
            return

        full_point_cloud = get_full_ply(
            session=session,
            step=step,
            source_base_path=os.path.join(source_base_path, trial.name),
            metashape_ply_generation_settings_id=metashape_ply_generation_settings_id,
            metashape_ply_export_settings_id=metashape_ply_export_settings_id,
            )
        
        if full_point_cloud:
            full_point_cloud_filepath = os.path.join(source_base_path, trial.name, full_point_cloud.file_name)

            o3d_plane_segmentaion_settings = session.query(Open3DSegmentationSetting).filter(Open3DSegmentationSetting.id == o3d_plane_segmentaion_settings_id).first()
            if not o3d_plane_segmentaion_settings:
                logging.info(f"Open3D Plane Segmentation Setting ID: {o3d_plane_segmentaion_settings_id} not found.")
                return
            o3d_plane_segmentaion_settings = o3d_plane_segmentaion_settings.__dict__


            color_avgs, color_stdevs = determine_plane_colors(
                full_ply_path=full_point_cloud_filepath,
                plane_limit=plane_limit,
                **o3d_plane_segmentaion_settings
            )
        else:
            logging.info("Cannot find Full PLY.")
            return