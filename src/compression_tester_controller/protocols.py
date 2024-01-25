from sqlalchemy.orm import sessionmaker

from compression_testing_data.meta import Session
from compression_testing_data.models.samples import Print, Sample
from compression_testing_data.models.testing import CompressionTrial


def add_test_print(session: Session):
    """
    only define non default entries for testing
    :param session:
    :return:
    """
    session.add(Print(
        name='new_print',
        filament_name='VarioShore',
        printer_model='Mk3s+',
        printer_settings_file='some_settings.ini',
        stl_file='my.stl'
    ))
    return session


def add_test_sample(session: Session, print_id: int):
    """
    only define non default entries for testing
    :param session:
    :return:
    """
    session.add(Sample(
        print_id=print_id
    ))
    return session


def add_test_trial(session: Session, sample_id: int):
    session.add(CompressionTrial(
        sample_id=sample_id
    ))
    return session


def create_steps(
        trial_id,
        target_strain_delta,
        min_strain,
        max_force
):

    return


def test_trial():
    session = Session()

    # clear tables to simulate starting from scratch
    models = [Print, Sample, CompressionTrial]
    for model in models:
        session.query(model).delete()
    session.commit()

    session = add_test_print(session=session)
    session.commit()
    print_id = session.query(Print).first().id

    # TODO need to complete sample, this can also be done post, since it involves volume:
    #   - essentially if a strain step target is 0 then we can derive the sample height and diam
    #   - add height after first scan?? or should this be in the steps or stl?
    session = add_test_sample(session=session, print_id=print_id)
    session.commit()
    sample_id = session.query(Sample).first().id

    session = add_test_trial(session=session, sample_id=sample_id)
    session.commit()

    # get force zero - get n samples from adc channel obs and avg before moving motor
    #   store in compression trial
    # find encoder zero - do we store this somewhere
    #   store on machine - add method to encoder class to reset encoder count at lower platon
    # make steps
    # run steps, run in order of descending strain
    #   move motor
    #       first step use special protocol to line up to sample
    #   complete step, record strain, force, etc
    #   transfer frames and make entries
    #   check entries using base dir in dir structure
    return


if __name__ == '__main__':
    test_trial()
