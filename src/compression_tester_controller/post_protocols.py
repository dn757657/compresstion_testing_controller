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
from compression_testing_data.models.testing import CompressionTrial, CompressionStep, Frame, MetashapeProject, FullPointCloud, ProcessedPointCloud, ProcessedSTL
from compression_testing_data.models.reconstruction_settings import MetashapePlyExportSetting, MetashapePlyGenerationSetting, Open3DDBSCANClusteringSetting, Open3DSegmentationSetting, ColorDefinition, MetashapeBuildModelSetting, ScalingFactor
from compression_testing_data.models.acquisition_settings import PlatonDimension

import pipelines
from pipelines import create_full_ply, process_full_ply, determine_plane_colors, build_stl, get_volume
from image_processing.utils import crop_image_by_color

from file_management import move_trial_assets,  move_file, bash_to_windows_paths

dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)


def add_reconstruction_defaults(session):
    session.add_all(
        [
            ColorDefinition(),
            MetashapeBuildModelSetting(),
            MetashapePlyExportSetting(),
            MetashapePlyGenerationSetting(),
            Open3DDBSCANClusteringSetting(),
            Open3DSegmentationSetting(),
            PlatonDimension()
        ]
    )
    session.commit()
    session.close()
    pass


def get_full_ply(
        session,
        step,
        source_base_path: str,
        metashape_ply_generation_settings_id: int,
        metashape_ply_export_settings_id: int,
        platon_side_color_setting_id: int,

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

    # full_point_clouds = step.full_point_clouds
    # for pcd in full_point_clouds:
    #     if (pcd.metashape_ply_export_setting_id == metashape_ply_export_settings_id) and (pcd.metashape_ply_generation_setting_id == metashape_ply_generation_settings_id):
    #         full_point_cloud = pcd 
    #         logging.info(f"Point Cloud Found @ ID: {full_point_cloud.id}")   

    platon_side_color_properties = session.query(ColorDefinition).filter(ColorDefinition.id == platon_side_color_setting_id).first()
    if not platon_side_color_properties:
        logging.info(f"Platon Side Color Setting ID: {platon_side_color_setting_id} not found.")
        return full_point_cloud
    platon_side_color_properties = platon_side_color_properties.__dict__

    platon_side_rgb_max = [
        platon_side_color_properties.get('red_mean_val') + (platon_side_color_properties.get('red_mean_stdv') * platon_side_color_properties.get('standard_dev_range')),
        platon_side_color_properties.get('green_mean_val') + (platon_side_color_properties.get('green_mean_stdv') * platon_side_color_properties.get('standard_dev_range')),
        platon_side_color_properties.get('blue_mean_val') + (platon_side_color_properties.get('blue_mean_stdv') * platon_side_color_properties.get('standard_dev_range')),
    ]
    platon_side_rgb_max = [value if value <= 255 else 255 for value in platon_side_rgb_max]

    platon_side_rgb_min = [
        platon_side_color_properties.get('red_mean_val') - (platon_side_color_properties.get('red_mean_stdv') * platon_side_color_properties.get('standard_dev_range')),
        platon_side_color_properties.get('green_mean_val') - (platon_side_color_properties.get('green_mean_stdv') * platon_side_color_properties.get('standard_dev_range')),
        platon_side_color_properties.get('blue_mean_val') - (platon_side_color_properties.get('blue_mean_stdv') * platon_side_color_properties.get('standard_dev_range')),
    ]
    platon_side_rgb_min = [value if value >= 0 else 0 for value in platon_side_rgb_min]
    
    full_point_clouds = step.full_point_clouds
    for pcd in full_point_clouds:
        if (pcd.metashape_ply_export_setting_id == metashape_ply_export_settings_id and 
            pcd.metashape_ply_generation_setting_id == metashape_ply_generation_settings_id):
            full_point_cloud = pcd 
            logging.info(f"Point Cloud Found @ ID: {full_point_cloud.id}")   


    frames = step.frames
    if not len(frames) > 0:
        logging.info(f"No Frames Assigned to Step ID: {step.id}")
        return full_point_cloud

    if not full_point_cloud:
        
        frame_paths = [os.path.join(source_base_path, frame.file_name).__str__() for frame in frames]
        cropped_frame_paths = []
        for frame in frame_paths:
            s = frame.split(".")
            dest_path=f'{".".join(s[:-1])}_crop.{s[-1]}'
            crop_image_by_color(
                source_path=frame,
                dest_path=dest_path,
                rgb_max=np.array(platon_side_rgb_max),
                rgb_min=np.array(platon_side_rgb_min)
            )
            cropped_frame_paths.append(dest_path)

        metashape_project_ext = 'psx'
        metashape_project_name = f'{uuid.uuid4()}'
        metashape_project_filename = f'{metashape_project_name}.{metashape_project_ext}'
        metashape_project_source_filepath = f'.\\{metashape_project_filename}'
        metashape_project_dest_filepath = f'{source_base_path}\\{metashape_project_filename}'

        metashape_project_files_source_filepath = f'.\\{metashape_project_name}.files'
        metashape_project_files_dest_filepath = f'{source_base_path}\\{metashape_project_name}.files'


        point_cloud_ext = 'ply'
        metashape_ply_name = f'{uuid.uuid4()}'
        metashape_ply_filename=f'{metashape_ply_name}.{point_cloud_ext}'
        metashape_ply_source_filepath=f'.\\{metashape_ply_filename}'
        metashape_ply_dest_filepath=f'{source_base_path}\\{metashape_ply_filename}'

        # for sim
        # with open(metashape_project_source_filepath, 'w') as file:
        #     file.write("")
        
        # with open(metashape_ply_source_filepath, 'w') as file:
        #     file.write("")

        create_full_ply(
            frames=cropped_frame_paths,
            metashape_point_cloud_gen_options=metashape_ply_gen_options,
            metashape_project_path=metashape_project_source_filepath,
            metashape_ply_path=metashape_ply_source_filepath,
        )

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

        move_file(source=metashape_project_files_source_filepath, destination=metashape_project_files_dest_filepath)

        full_point_clouds = step.full_point_clouds
        for pcd in full_point_clouds:
            if (pcd.metashape_ply_export_setting_id == metashape_ply_export_settings_id) and (pcd.metashape_ply_generation_setting_id == metashape_ply_generation_settings_id):
                full_point_cloud = pcd 
                logging.info(f"Point Cloud Found @ ID: {full_point_cloud.id}")  

        # for dest_path in cropped_frame_paths:
        #         if os.path.exists(dest_path):
        #             os.remove(dest_path)

    return full_point_cloud


def get_processed_ply(
        session,
        step,
        o3d_plane_segmentaion_settings_id: int,
        o3d_dbscan_clustering_settings_id: int,
        platon_dims_id: int,
        platon_side_color_setting_id: int,
        platon_face_color_setting_id: int,
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

    platon_side_color_properties = session.query(ColorDefinition).filter(ColorDefinition.id == platon_side_color_setting_id).first()
    if not platon_side_color_properties:
        logging.info(f"Platon Side Color Setting ID: {platon_side_color_setting_id} not found.")
        return processed_point_cloud
    platon_side_color_properties = platon_side_color_properties.__dict__

    platon_face_color_properties = session.query(ColorDefinition).filter(ColorDefinition.id == platon_face_color_setting_id).first()
    if not platon_face_color_properties:
        logging.info(f"Platon Face Color Setting ID: {platon_side_color_setting_id} not found.")
        return processed_point_cloud
    platon_face_color_properties = platon_face_color_properties.__dict__

    platon_side_rgb_max = [
        platon_side_color_properties.get('red_mean_val') + (platon_side_color_properties.get('red_mean_stdv') * platon_side_color_properties.get('standard_dev_range')),
        platon_side_color_properties.get('green_mean_val') + (platon_side_color_properties.get('green_mean_stdv') * platon_side_color_properties.get('standard_dev_range')),
        platon_side_color_properties.get('blue_mean_val') + (platon_side_color_properties.get('blue_mean_stdv') * platon_side_color_properties.get('standard_dev_range')),
    ]
    platon_side_rgb_max = [value if value <= 255 else 255 for value in platon_side_rgb_max]

    platon_side_rgb_min = [
        platon_side_color_properties.get('red_mean_val') - (platon_side_color_properties.get('red_mean_stdv') * platon_side_color_properties.get('standard_dev_range')),
        platon_side_color_properties.get('green_mean_val') - (platon_side_color_properties.get('green_mean_stdv') * platon_side_color_properties.get('standard_dev_range')),
        platon_side_color_properties.get('blue_mean_val') - (platon_side_color_properties.get('blue_mean_stdv') * platon_side_color_properties.get('standard_dev_range')),
    ]
    platon_side_rgb_min = [value if value >= 0 else 0 for value in platon_side_rgb_min]

    platon_face_rgb_max = [
        platon_face_color_properties.get('red_mean_val') + (platon_face_color_properties.get('red_mean_stdv') * platon_face_color_properties.get('standard_dev_range')),
        platon_face_color_properties.get('green_mean_val') + (platon_face_color_properties.get('green_mean_stdv') * platon_face_color_properties.get('standard_dev_range')),
        platon_face_color_properties.get('blue_mean_val') + (platon_face_color_properties.get('blue_mean_stdv') * platon_face_color_properties.get('standard_dev_range')),
    ]
    platon_face_rgb_max = [value if value <= 255 else 255 for value in platon_face_rgb_max]

    platon_face_rgb_min = [
        platon_face_color_properties.get('red_mean_val') - (platon_face_color_properties.get('red_mean_stdv') * platon_face_color_properties.get('standard_dev_range')),
        platon_face_color_properties.get('green_mean_val') - (platon_face_color_properties.get('green_mean_stdv') * platon_face_color_properties.get('standard_dev_range')),
        platon_face_color_properties.get('blue_mean_val') - (platon_face_color_properties.get('blue_mean_stdv') * platon_face_color_properties.get('standard_dev_range')),
    ]
    platon_face_rgb_min = [value if value >= 0 else 0 for value in platon_face_rgb_min]

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

        # if is_calibration:
        #     num_platons = 1
        # else:
        num_platons = 2

        # for sim
        # with open(processed_ply_source_filepath, 'w') as file:
        #     file.write("")
        # scaling_factor = 5

        scaling_factor = process_full_ply(
            full_ply_path=full_ply_filepath,
            processed_ply_path=processed_ply_source_filepath,
            num_platons=num_platons,
            o3d_plane_segmentaion_settings=o3d_plane_segmentaion_settings,
            o3d_dbscan_clustering_settings=o3d_dbscan_clustering_settings,
            known_platon_dims=platon_dimensions,
            platon_side_rgb_max=platon_side_rgb_max,
            platon_side_rgb_min=platon_side_rgb_min,
            platon_face_rgb_max=platon_face_rgb_max,
            platon_face_rgb_min=platon_face_rgb_min
        )        

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


def get_stl(
        session,
        step,
        ply_scaling_factor: float,
        stl_scaling_factor_id: int,
        source_base_path: str,
        full_ply_path: str,
        metashape_stl_generation_settings_id: int,
):
    processed_stl = None

    metashape_stl_gen_options = session.query(MetashapeBuildModelSetting).filter(MetashapeBuildModelSetting.id == metashape_stl_generation_settings_id).first()
    if not metashape_stl_gen_options:
        logging.info(f"Metashape STL Generation Setting ID: {metashape_stl_generation_settings_id} not found.")
        return processed_stl
    metashape_stl_gen_options = metashape_stl_gen_options.__dict__

    stl_scaling_factor = session.query(ScalingFactor).filter(ScalingFactor.id == stl_scaling_factor_id).first()
    if not stl_scaling_factor:
        logging.info(f"STL Scaling Factor ID: {stl_scaling_factor_id} not found.")
        return processed_stl
    stl_scaling_factor = stl_scaling_factor.__dict__
    stl_scaling_factor = stl_scaling_factor.get('scaling_factor')

    stls = step.stls
    for stl in stls:
        if (stl.scaling_factor_id == stl_scaling_factor_id and 
            stl.metahsape_build_model_setting_id == metashape_stl_generation_settings_id):
            processed_stl = stl 
            logging.info(f"STL Found @ ID: {processed_stl.id}") 

    if not processed_stl:
        
        processed_stl_ext = 'stl'
        processed_stl_name = f'{uuid.uuid4()}'
        processed_stl_filename = f'{processed_stl_name}.{processed_stl_ext}'
        processed_stl_source_filepath = f'.\\{processed_stl_filename}'
        processed_stl_dest_filepath = f'{source_base_path}\\{processed_stl_filename}'

        build_stl(
            full_ply_path=full_ply_path,
            stl_write_path=processed_stl_source_filepath,
            metashape_stl_generation_settings=metashape_stl_gen_options
        )

        volume = get_volume(
            scaling_factor=ply_scaling_factor,
            stl_path=processed_stl_source_filepath
        )
        volume = volume * stl_scaling_factor

        move_file(source=processed_stl_source_filepath, destination=processed_stl_dest_filepath)
        new_stl = ProcessedSTL(
            name=processed_stl_name,
            file_extension=processed_stl_ext,
            file_name=processed_stl_filename,
            volume=volume,
            volume_unit='mm3',
            scaling_factor_id=stl_scaling_factor_id,
            metahsape_build_model_setting_id=metashape_stl_generation_settings_id,
            compression_step_id=step.id
        )
        session.add(new_stl)
        session.commit()

        stls = step.stls
        for stl in stls:
            if (stl.metahsape_build_model_setting_id == metashape_stl_generation_settings_id):
                processed_stl = stl 
                logging.info(f"Processed STL Found @ ID: {processed_stl.id}")  

    return processed_stl


def process_trial(
        trial_id: int,
        metashape_ply_generation_settings_id: int,
        metashape_ply_export_settings_id: int,
        metashape_stl_generation_settings_id: int,
        o3d_plane_segmentaion_settings_id: int,
        o3d_dbscan_clustering_settings_id: int,
        platon_side_color_setting_id: int,
        platon_face_color_setting_id: int,
        platon_dims_id: int,
        stl_scaling_factor_id: int,
        db_conn: str,
        source_base_path: str,
        ):
    
    Session = get_session(conn_str=db_conn)
    session = Session()
    trial = session.query(CompressionTrial).filter(CompressionTrial.id == trial_id).first()
    
    if trial:
        logging.info(f"Processing Trial: {trial.id}")
        steps  = trial.steps
        if len(steps) > 0:
            steps = sorted(steps, key=lambda x: x.strain_target)

            i = 0
            for step in steps:
                logging.info(f"Processing Step {step.id}: {i} / {len(steps)}")
                i += 1
                frames = step.frames
                if not len(frames) > 0:  # check for frames, cant create anything without frames
                    logging.info(f"No Frames assigned to Step ID: {step.name}")
                    continue

                # check if all options exist
                
                
                # to check for assets try inserting and rely on unique conditions to reject insertion?
                # if asset exists get its filepath to use in processing
                # make sure all options are accessible

                # gen point clouds
                # source_base_path = os.path.join(source_base_path, trial.name)
                full_point_cloud = get_full_ply(
                    session=session,
                    step=step,
                    platon_side_color_setting_id=platon_side_color_setting_id,
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
                        platon_side_color_setting_id=platon_side_color_setting_id,
                        platon_face_color_setting_id=platon_face_color_setting_id,
                        source_base_path=os.path.join(source_base_path, trial.name),
                        platon_dims_id=platon_dims_id,
                        full_ply_filepath=full_point_cloud_filepath,
                    )

                    if processed_ply:
                        processed_ply_filepath = os.path.join(source_base_path, trial.name, processed_ply.file_name)

                        stl = get_stl(
                            session=session,
                            step=step,
                            ply_scaling_factor=processed_ply.scaling_factor,
                            stl_scaling_factor_id=stl_scaling_factor_id,
                            source_base_path=os.path.join(source_base_path, trial.name),
                            full_ply_path=processed_ply_filepath,
                            metashape_stl_generation_settings_id=metashape_stl_generation_settings_id, 
                        )
                    
                # create stls
        session.close()

    pass


def determine_plane_colors(
        step_id: int,
        metashape_ply_generation_settings_id: int,
        metashape_ply_export_settings_id: int,
        o3d_plane_segmentaion_settings_id: int,
        db_conn: str,
        source_base_path: str,
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


            color_stats = pipelines.determine_plane_colors(
                full_ply_path=full_point_cloud_filepath,
                **o3d_plane_segmentaion_settings
            )

            for color in color_stats.keys():
                color_rgb_avgs = color.get('average_color')
                color_rgb_stdevs = color.get('std_dev_color')

                new_color = ColorDefinition(
                    color=color,
                    red_mean_val=color_rgb_avgs[0],
                    blue_mean_val=color_rgb_avgs[1],
                    green_mean_val=color_rgb_avgs[2],
                    red_mean_stdv=color_rgb_stdevs[0],
                    blue_mean_stdv=color_rgb_stdevs[1],
                    green_mean_stdv=color_rgb_stdevs[2],
                )
                session.add(new_color)
            session.commit()
            session.close()
        else:
            logging.info("Cannot find Full PLY.")
            return