"""Tests for tscat_driver actions and entity cache."""
import datetime as dt

from tscat import _Catalogue, _Event

from tscat_gui.tscat_driver.actions import (
    AddEventsToCatalogueAction,
    CreateEntityAction,
    DeletePermanentlyAction,
    GetCatalogueAction,
    GetCataloguesAction,
    RestorePermanentlyDeletedAction,
    SetAttributeAction,
)


class TestEntityCache:
    """Bug #3: RestorePermanentlyDeletedAction must populate entity cache."""

    def test_create_entity_populates_cache(self, driver, wait_for_action):
        action = wait_for_action(CreateEntityAction(None, _Catalogue, {
            'name': 'Test', 'author': 'test'
        }))
        assert action.entity.uuid in driver._entity_cache

    def test_get_catalogues_populates_cache(self, driver, wait_for_action):
        create = wait_for_action(CreateEntityAction(None, _Catalogue, {
            'name': 'Test', 'author': 'test'
        }))
        driver._entity_cache.clear()

        wait_for_action(GetCataloguesAction(None, False))
        assert create.entity.uuid in driver._entity_cache

    def test_get_catalogue_events_populates_cache(self, driver, wait_for_action):
        cat = wait_for_action(CreateEntityAction(None, _Catalogue, {
            'name': 'Test', 'author': 'test'
        }))
        evt = wait_for_action(CreateEntityAction(None, _Event, {
            'start': dt.datetime.now(), 'stop': dt.datetime.now(), 'author': 'test'
        }))
        wait_for_action(AddEventsToCatalogueAction(None, [evt.entity.uuid], cat.entity.uuid))
        driver._entity_cache.clear()

        wait_for_action(GetCatalogueAction(None, uuid=cat.entity.uuid))
        assert evt.entity.uuid in driver._entity_cache

    def test_restore_permanently_deleted_populates_cache(self, driver, wait_for_action):
        """Reproducer for bug #3: undo of permanent delete must update cache."""
        cat = wait_for_action(CreateEntityAction(None, _Catalogue, {
            'name': 'Test', 'author': 'test'
        }))

        delete_action = wait_for_action(DeletePermanentlyAction(None, [cat.entity.uuid]))

        # Clear cache to simulate the state after permanent deletion
        driver._entity_cache.clear()

        restore_action = wait_for_action(
            RestorePermanentlyDeletedAction(None, delete_action.deleted_entities)
        )
        restored_uuid = restore_action.deleted_entities[0].restored_entity.uuid
        assert restored_uuid in driver._entity_cache

    def test_set_attribute_updates_cache(self, driver, wait_for_action):
        cat = wait_for_action(CreateEntityAction(None, _Catalogue, {
            'name': 'Test', 'author': 'test'
        }))
        uuid = cat.entity.uuid

        wait_for_action(SetAttributeAction(None, [uuid], 'name', ['Updated']))
        assert driver._entity_cache[uuid].name == 'Updated'


class TestRestorePermanentlyDeleted:
    """Bugs #1-2: assert all(lambda...) and add_events_to_catalogue(c, entity)."""

    def test_restore_catalogue_with_events(self, wait_for_action):
        """Restore a permanently deleted catalogue that had events linked."""
        cat = wait_for_action(CreateEntityAction(None, _Catalogue, {
            'name': 'Cat', 'author': 'test'
        }))
        evt = wait_for_action(CreateEntityAction(None, _Event, {
            'start': dt.datetime.now(), 'stop': dt.datetime.now(), 'author': 'test'
        }))
        wait_for_action(AddEventsToCatalogueAction(None, [evt.entity.uuid], cat.entity.uuid))

        delete_action = wait_for_action(DeletePermanentlyAction(None, [cat.entity.uuid]))

        # This would crash before fix: assert all(lambda...) was always true,
        # masking type errors
        restore_action = wait_for_action(
            RestorePermanentlyDeletedAction(None, delete_action.deleted_entities)
        )
        assert restore_action.deleted_entities[0].restored_entity is not None

    def test_restore_event_with_catalogues(self, wait_for_action):
        """Restore a permanently deleted event that was linked to catalogues.

        Before fix: add_events_to_catalogue(c, entity) passed bare event, not list.
        """
        cat = wait_for_action(CreateEntityAction(None, _Catalogue, {
            'name': 'Cat', 'author': 'test'
        }))
        evt = wait_for_action(CreateEntityAction(None, _Event, {
            'start': dt.datetime.now(), 'stop': dt.datetime.now(), 'author': 'test'
        }))
        wait_for_action(AddEventsToCatalogueAction(None, [evt.entity.uuid], cat.entity.uuid))

        delete_action = wait_for_action(DeletePermanentlyAction(None, [evt.entity.uuid]))

        restore_action = wait_for_action(
            RestorePermanentlyDeletedAction(None, delete_action.deleted_entities)
        )
        assert restore_action.deleted_entities[0].restored_entity is not None
