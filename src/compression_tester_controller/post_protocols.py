import logging
import uuid
import os
import glob
import pymeshfix

logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)

import numpy as np
from dotenv import load_dotenv
from os.path import join, dirname

from compression_testing_data.meta import get_session
from compression_testing_data.models.testing import CompressionTrial, CompressionStep, Frame, MetashapeProject, FullPointCloud, ProcessedPointCloud, RawSTL, ProcessedSTL
from compression_testing_data.models.reconstruction_settings import MetashapePlyExportSetting, MetashapePlyGenerationSetting, Open3DDBSCANClusteringSetting, Open3DSegmentationSetting, ColorDefinition, MetashapeBuildModelSetting, ScalingFactor
from compression_testing_data.models.acquisition_settings import PlatonDimension
from compression_testing_data.models.samples import Phantom

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
        make_full_ply: bool = True

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

    if not full_point_cloud and make_full_ply:
        
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


def get_raw_stl(
        session,
        step,
        processed_ply,
        ply_scaling_factor: float,
        stl_scaling_factor_id: int,
        source_base_path: str,
        full_ply_path: str,
        metashape_stl_generation_settings_id: int,
):
    raw_stl = None

    metashape_stl_gen_options = session.query(MetashapeBuildModelSetting).filter(MetashapeBuildModelSetting.id == metashape_stl_generation_settings_id).first()
    if not metashape_stl_gen_options:
        logging.info(f"Metashape STL Generation Setting ID: {metashape_stl_generation_settings_id} not found.")
        return raw_stl
    metashape_stl_gen_options = metashape_stl_gen_options.__dict__

    stl_scaling_factor = session.query(ScalingFactor).filter(ScalingFactor.id == stl_scaling_factor_id).first()
    if not stl_scaling_factor:
        logging.info(f"STL Scaling Factor ID: {stl_scaling_factor_id} not found.")
        return raw_stl
    stl_scaling_factor = stl_scaling_factor.__dict__
    stl_scaling_factor = stl_scaling_factor.get('scaling_factor')

    stls = step.raw_stls
    for stl in stls:
        if (stl.scaling_factor_id == stl_scaling_factor_id and 
            stl.metahsape_build_model_setting_id == metashape_stl_generation_settings_id and
            stl.processed_point_cloud_id == processed_ply.id):
            raw_stl = stl 
            logging.info(f"Raw STL Found @ ID: {raw_stl.id}") 

    if not raw_stl:
        
        raw_stl_ext = 'stl'
        raw_stl_name = f'{uuid.uuid4()}'
        raw_stl_filename = f'{raw_stl_name}.{raw_stl_ext}'
        raw_stl_source_filepath = f'.\\{raw_stl_filename}'
        raw_stl_dest_filepath = f'{source_base_path}\\{raw_stl_filename}'

        build_stl(
            full_ply_path=full_ply_path,
            stl_write_path=raw_stl_source_filepath,
            metashape_stl_generation_settings=metashape_stl_gen_options
        )

        volume = get_volume(
            scaling_factor=ply_scaling_factor,
            stl_path=raw_stl_source_filepath
        )
        volume = volume * stl_scaling_factor
        volume = abs(volume)

        move_file(source=raw_stl_source_filepath, destination=raw_stl_dest_filepath)
        new_stl = RawSTL(
            name=raw_stl_name,
            file_extension=raw_stl_ext,
            file_name=raw_stl_filename,
            volume=volume,
            volume_unit='mm3',
            scaling_factor_id=stl_scaling_factor_id,
            metahsape_build_model_setting_id=metashape_stl_generation_settings_id,
            compression_step_id=step.id,
            processed_point_cloud_id=processed_ply.id
        )
        session.add(new_stl)
        session.commit()

        stls = step.raw_stls
        for stl in stls:
            if (stl.metahsape_build_model_setting_id == metashape_stl_generation_settings_id):
                raw_stl = stl 
                logging.info(f"Raw STL Found @ ID: {raw_stl.id}")  

    return raw_stl


def get_processed_stl(
        session,
        step,
        raw_stl,
        raw_stl_filepath: str,
        source_base_path: str,
):
    processed_stl = None

    # since we can only have one processed stl per raw stl
    if raw_stl.processed_stl: 
        processed_stl = raw_stl.processed_stl[0] 
        logging.info(f"Processed STL Found @ ID: {processed_stl.id}") 

    if not processed_stl:
        
        processed_stl_ext = 'stl'
        processed_stl_name = f'{uuid.uuid4()}'
        processed_stl_filename = f'{processed_stl_name}.{processed_stl_ext}'
        processed_stl_dest_filepath = f'{source_base_path}\\{processed_stl_filename}'

        logging.info(f"Cleaning and Sealing STL...")
        pymeshfix.clean_from_file(raw_stl_filepath, processed_stl_dest_filepath)
        
        scaling_factor = raw_stl.processed_point_cloud.scaling_factor
        volume = get_volume(
            scaling_factor=scaling_factor,  # no scaling since scaled already
            stl_path=processed_stl_dest_filepath
        )
        volume = abs(volume)

        new_stl = ProcessedSTL(
            name=processed_stl_name,
            file_extension=processed_stl_ext,
            file_name=processed_stl_filename,
            volume=volume,
            volume_unit='mm3',
            compression_step_id=step.id,
            raw_stl_id=raw_stl.id
        )
        session.add(new_stl)
        session.commit()

        if raw_stl.processed_stl: 
            processed_stl = raw_stl.processed_stl[0]
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
        make_full_ply: bool = True,
        make_processed_ply: bool = True,
        make_raw_stl: bool = True,
        make_processed_stl: bool = True
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
                # if step.id != 114:
                #     continue 

                logging.info(f"Processing Step {step.id}: {i + 1} / {len(steps)}")
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
                    session =session,
                    step=step,
                    platon_side_color_setting_id=platon_side_color_setting_id,
                    source_base_path=os.path.join(source_base_path, trial.name),
                    metashape_ply_generation_settings_id=metashape_ply_generation_settings_id,
                    metashape_ply_export_settings_id=metashape_ply_export_settings_id,
                    make_full_ply=make_full_ply
                )

                if full_point_cloud and make_processed_ply:
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

                    if processed_ply and make_raw_stl:
                        processed_ply_filepath = os.path.join(source_base_path, trial.name, processed_ply.file_name)

                        raw_stl = get_raw_stl(
                            session=session,
                            step=step,
                            processed_ply=processed_ply,
                            ply_scaling_factor=processed_ply.scaling_factor,
                            stl_scaling_factor_id=stl_scaling_factor_id,
                            source_base_path=os.path.join(source_base_path, trial.name),
                            full_ply_path=processed_ply_filepath,
                            metashape_stl_generation_settings_id=metashape_stl_generation_settings_id, 
                        )
                            
                        if raw_stl and make_processed_stl:
                            raw_stl_filepath = os.path.join(source_base_path, trial.name, raw_stl.file_name)

                            processed_stl = get_processed_stl(
                                session=session,
                                step=step,
                                raw_stl=raw_stl,
                                source_base_path=os.path.join(source_base_path, trial.name),
                                raw_stl_filepath=raw_stl_filepath,
                            )

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
        

def get_calibration_constant(db_conn, phantom_ids):
    Session = get_session(conn_str=db_conn)
    session = Session()

    for id in phantom_ids:
        phantom = session.query(Phantom).filter(Phantom.id == id).first()

        trials = list()
        for trial in session.query(CompressionTrial).filter(CompressionTrial.phantom_id == id).all():
            trials.append(trial)

        steps = list()
        for trial in trials:
            steps += trial.steps

        processed_stls = list()
        raw_stls = list()
        for steps in steps:
            processed_stls += steps.processed_stls
            raw_stls += steps.raw_stls
        
        processed_volumes = list()
        raw_volumes = list()
        for stl in processed_stls:
            processed_volumes.append(stl.volume)
        for stl in raw_stls:
            raw_volumes.append(stl.volume)

        processed_volumes = np.array(processed_volumes)
        raw_volumes = np.array(raw_volumes)

        p_volume_mean = np.mean(processed_volumes)
        r_volume_mean = np.mean(raw_volumes)

        p_volume_stdev = np.std(processed_volumes)
        r_volume_stdev = np.std(raw_volumes)

        p_cal_const = phantom.volume / p_volume_mean
        r_cal_const = phantom.volume / r_volume_mean
        print()

    return