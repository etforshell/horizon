# Copyright 2013 Nebula, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from collections import OrderedDict

from django.utils.translation import ugettext_lazy as _

from horizon import exceptions
from horizon.tables import PagedTableMixin
from horizon import tabs

from openstack_dashboard import api

from openstack_dashboard.dashboards.project.volumes.volumes \
    import tables as volume_tables


class VolumeTableMixIn(object):
    _has_more_data = False
    _has_prev_data = False

    def _get_volumes(self, search_opts=None):
        try:
            marker, sort_dir = self._get_marker()
            volumes, self._has_more_data, self._has_prev_data = \
                api.cinder.volume_list_paged(self.request, marker=marker,
                                             search_opts=search_opts,
                                             sort_dir=sort_dir, paginate=True)

            if sort_dir == "asc":
                volumes.reverse()

            return volumes
        except Exception:
            exceptions.handle(self.request,
                              _('Unable to retrieve volume list.'))
            return []

    def _get_instances(self, search_opts=None, instance_ids=None):
        if not instance_ids:
            return []
        try:
            # TODO(tsufiev): we should pass attached_instance_ids to
            # nova.server_list as soon as Nova API allows for this
            instances, has_more = api.nova.server_list(self.request,
                                                       search_opts=search_opts,
                                                       detailed=False)
            return instances
        except Exception:
            exceptions.handle(self.request,
                              _("Unable to retrieve volume/instance "
                                "attachment information"))
            return []

    def _get_volumes_ids_with_snapshots(self, search_opts=None):
        try:
            volume_ids = []
            snapshots = api.cinder.volume_snapshot_list(
                self.request, search_opts=search_opts)
            if snapshots:
                # extract out the volume ids
                volume_ids = set([(s.volume_id) for s in snapshots])
        except Exception:
            exceptions.handle(self.request,
                              _("Unable to retrieve snapshot list."))

        return volume_ids

    def _get_attached_instance_ids(self, volumes):
        attached_instance_ids = []
        for volume in volumes:
            for att in volume.attachments:
                server_id = att.get('server_id', None)
                if server_id is not None:
                    attached_instance_ids.append(server_id)
        return attached_instance_ids

    # set attachment string and if volume has snapshots
    def _set_volume_attributes(self,
                               volumes,
                               instances,
                               volume_ids_with_snapshots):
        instances = OrderedDict([(inst.id, inst) for inst in instances])
        for volume in volumes:
            if volume_ids_with_snapshots:
                if volume.id in volume_ids_with_snapshots:
                    setattr(volume, 'has_snapshot', True)
            if instances:
                for att in volume.attachments:
                    server_id = att.get('server_id', None)
                    att['instance'] = instances.get(server_id, None)


class VolumeTab(PagedTableMixin, tabs.TableTab, VolumeTableMixIn):
    table_classes = (volume_tables.VolumesTable,)
    name = _("Volumes")
    slug = "volumes_tab"
    template_name = ("horizon/common/_detail_table.html")
    preload = False

    def get_volumes_data(self):
        volumes = self._get_volumes()
        attached_instance_ids = self._get_attached_instance_ids(volumes)
        instances = self._get_instances(instance_ids=attached_instance_ids)
        volume_ids_with_snapshots = self._get_volumes_ids_with_snapshots()
        self._set_volume_attributes(
            volumes, instances, volume_ids_with_snapshots)
        return volumes


class VolumeAndSnapshotTabs(tabs.TabGroup):
    slug = "volumes_and_snapshots"
    tabs = (VolumeTab, )
    sticky = True
