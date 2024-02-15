import uuid

from compression_testing_data.models.samples import Print, Sample
from compression_testing_data.models.acquisition_settings import CameraSetting
from compression_testing_data.models.testing import CompressionTrial
from compression_testing_data.sim import add_test_print, add_test_sample, add_test_trial
from compression_testing_data.meta import get_session

from compression_tester_controls.components.canon_eosr50 import eosr50_init, eosr50_continuous_capture_and_save, gphoto2_get_active_ports


CONN_STR = 'postgresql://domanlab:dn757657@192.168.1.2:5432/compression_testing'


def add_default_camera_params():
    Session = get_session(conn_str=CONN_STR)

    if Session:
        session = Session()
        default_settings = CameraSetting(
            autopoweroff=0,
            capture=0, imageformat=22, iso=10,
            focusmode=0,
            aspectratio=0,
            aperture=4,
            shutterspeed=37
        )

        session.add(default_settings)
        session.commit()
    
    pass


def full_test_trial():
    Session = get_session(conn_str=CONN_STR)

    if Session:  # generate some bogus db info
        session = Session()

        print_id = 1
        result = session.query(Print).filter(Print.id == print_id).first()
        if not result:
            add_test_print(session=session)
            session.commit()

        sample_id = 1
        result = session.query(Sample).filter(Sample.id == sample_id).first()
        if not result:
            add_test_sample(session=session, print_id=print_id)
            session.commit()

        trial_id = 1
        result = session.query(CompressionTrial).filter(CompressionTrial.id == trial_id).first()
        if not result:
            add_test_trial(session=session, sample_id=sample_id, name=uuid.uuid4())
            session.commit()

        # take some pics and transfer them, make entries
    
    return


def testing():
    trial_id = 1
    Session = get_session(conn_str=CONN_STR)
    session = Session()

    trial = session.query(CompressionTrial).filter(CompressionTrial.id == trial_id).first()
    sample_id = trial.sample.id
    sample = session.query(Sample).filter(Sample.id == trial.sample.id).first()

    return

if __name__ == '__main__':
    full_test_trial()
