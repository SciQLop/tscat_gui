import tscat

from typing import Union


# this function should go to tscat - this is a kludge to work-around missing functions or wrong concepts
# get an entity from a UUID (catalogue or event)
# get an entity from a UUID independently whether it is removed (in trash) or not
def get_entity_from_uuid_safe(uuid: str) -> Union[tscat.Catalogue, tscat.Event]:
    catalogues = tscat.get_catalogues(tscat.filtering.UUID(uuid))
    if len(catalogues) == 1:
        return catalogues[0]
    elif len(catalogues) == 0:
        catalogues = tscat.get_catalogues(tscat.filtering.UUID(uuid), removed_items=True)
        if len(catalogues) == 1:
            return catalogues[0]
        elif len(catalogues) == 0:
            events = tscat.get_events(tscat.filtering.UUID(uuid))
            if len(events) == 1:
                return events[0]
            elif len(events) == 0:
                events = tscat.get_events(tscat.filtering.UUID(uuid), removed_items=True)
                if len(events) == 1:
                    return events[0]

    raise ValueError("No entity (catalogue or event) found for this UUID")
