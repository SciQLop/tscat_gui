from typing import List, cast

import tscat

from .model_base.constants import EntityRole


def __total_event_count(catalogues: List[tscat._Catalogue]) -> str:
    from .tscat_driver.model import tscat_model
    return str(sum(tscat_model.catalog(c.uuid).rowCount() for c in catalogues))


def __global_start_stop_range(catalogues: List[tscat._Catalogue]) -> str:
    from .tscat_driver.model import tscat_model
    min_start, max_stop = None, None
    for c in catalogues:
        model = tscat_model.catalog(c.uuid)
        for i in range(model.rowCount()):
            event = cast(tscat._Event, model.data(model.index(i, 0), EntityRole))

            assert event is not None

            if min_start is None or event.start < min_start:
                min_start = event.start
            if max_stop is None or event.stop > max_stop:
                max_stop = event.stop

    if None in (min_start, max_stop):
        return '-'
    return f'between {min_start} and {max_stop}'


catalogue_meta_data = {
    "Total Events": __total_event_count,
    # "Global Start/Stop": __global_start_stop_range,
}
