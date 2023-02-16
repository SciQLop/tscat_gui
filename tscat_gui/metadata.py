from typing import List

import tscat


def __total_event_count(catalogues: List[tscat._Catalogue]) -> str:
    filter = tscat.filtering.Any(*(tscat.filtering.InCatalogue(catalogue) for catalogue in catalogues))
    return str(len(tscat.get_events(filter)))


def __global_start_stop_range(catalogues: List[tscat._Catalogue]) -> str:
    filter = tscat.filtering.Any(*(tscat.filtering.InCatalogue(catalogue) for catalogue in catalogues))

    min_start, max_stop = None, None
    for event in tscat.get_events(filter):
        if min_start is None or event.start < min_start:
            min_start = event.start
        if max_stop is None or event.stop > max_stop:
            max_stop = event.stop

    if None in (min_start, max_stop):
        return '-'
    return f'between {min_start} and {max_stop}'


catalogue_meta_data = {
    "Total Events": __total_event_count,
    "Global Start/Stop": __global_start_stop_range,
}
