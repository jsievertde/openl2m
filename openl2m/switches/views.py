#
# This file is part of Open Layer 2 Management (OpenL2M).
#
# OpenL2M is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License version 3 as published by
# the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for
# more details.  You should have received a copy of the GNU General Public
# License along with OpenL2M. If not, see <http://www.gnu.org/licenses/>.
#
import sys
import os
import distro
import time
import datetime
import traceback
import re

import django
from django.conf import settings
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.utils.html import mark_safe
from django.utils import timezone
from django.core.paginator import Paginator
from django.shortcuts import redirect
from django.template import Template, Context
from django.contrib import messages

from switches.connect.classes import Error
from switches.models import (
    SnmpProfile,
    NetmikoProfile,
    Command,
    CommandList,
    CommandTemplate,
    VLAN,
    VlanGroup,
    Switch,
    SwitchGroup,
    Log,
)
from switches.constants import (
    LOG_TYPE_VIEW,
    LOG_TYPE_CHANGE,
    LOG_TYPE_ERROR,
    LOG_TYPE_COMMAND,
    LOG_TYPE_CHOICES,
    LOG_ACTION_CHOICES,
    LOG_CHANGE_INTERFACE_DOWN,
    LOG_CHANGE_INTERFACE_UP,
    LOG_CHANGE_INTERFACE_POE_DOWN,
    LOG_CHANGE_INTERFACE_POE_UP,
    LOG_CHANGE_INTERFACE_POE_TOGGLE_DOWN_UP,
    LOG_CHANGE_INTERFACE_PVID,
    LOG_CHANGE_INTERFACE_ALIAS,
    LOG_CHANGE_BULK_EDIT,
    LOG_VIEW_SWITCHGROUPS,
    LOG_CONNECTION_ERROR,
    LOG_BULK_EDIT_TASK_START,
    LOG_VIEW_SWITCH,
    LOG_VIEW_ALL_LOGS,
    LOG_VIEW_ADMIN_STATS,
    LOG_VIEW_SWITCH_SEARCH,
    LOG_EXECUTE_COMMAND,
    LOG_SAVE_SWITCH,
    LOG_RELOAD_SWITCH,
    INTERFACE_STATUS_NONE,
    BULKEDIT_POE_NONE,
    BULKEDIT_POE_CHOICES,
    BULKEDIT_ALIAS_TYPE_CHOICES,
    BULKEDIT_INTERFACE_CHOICES,
    BULKEDIT_ALIAS_TYPE_REPLACE,
    BULKEDIT_ALIAS_TYPE_APPEND,
    BULKEDIT_POE_DOWN_UP,
    BULKEDIT_POE_CHANGE,
    BULKEDIT_POE_DOWN,
    BULKEDIT_POE_UP,
    SWITCH_STATUS_ACTIVE,
    LOG_TYPE_WARNING,
    INTERFACE_STATUS_CHANGE,
    INTERFACE_STATUS_DOWN,
    INTERFACE_STATUS_UP,
    LOG_VLAN_CREATE,
    LOG_VLAN_EDIT,
    LOG_VLAN_DELETE,
)
from switches.connect.connector import clear_switch_cache
from switches.connect.connect import get_connection_object
from switches.connect.constants import (
    POE_PORT_ADMIN_ENABLED,
    POE_PORT_ADMIN_DISABLED,
)
from switches.utils import (
    success_page,
    warning_page,
    error_page,
    dprint,
    get_from_http_session,
    save_to_http_session,
    get_remote_ip,
    time_duration,
    string_contains_regex,
    string_matches_regex,
    get_choice_name,
)
from users.utils import user_can_bulkedit, user_can_edit_vlans, get_current_users
from counters.models import Counter, counter_increment
from counters.constants import (
    COUNTER_CHANGES,
    COUNTER_BULKEDITS,
    COUNTER_ERRORS,
    COUNTER_ACCESS_DENIED,
    COUNTER_COMMANDS,
    COUNTER_VIEWS,
    COUNTER_DETAILVIEWS,
    COUNTER_HWINFO,
    COUNTER_VLAN_MANAGE,
)
from notices.models import Notice

# rest_framework
from django.contrib.auth.mixins import LoginRequiredMixin
from rest_framework.authentication import SessionAuthentication, BasicAuthentication, TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status


@login_required(redirect_field_name=None)
def switches(request):
    """
    This is the "home view", at "/"
    It shows the list of switches a user has access to
    """

    template_name = "home.html"

    # back to the home screen, clear session cache
    # so we re-read switches as needed
    clear_switch_cache(request)

    # save remote ip in session, so we can use it in current user display!
    save_to_http_session(request, "remote_ip", get_remote_ip(request))

    # find the groups with switches that we have rights to:
    switchgroups = {}
    permissions = {}
    if request.user.is_superuser or request.user.is_staff:
        # optimize data queries, get all related field at once!
        groups = SwitchGroup.objects.all().order_by("name")

    else:
        # figure out what this user has access to.
        # Note we use the ManyToMany 'related_name' attribute for readability!
        groups = request.user.switchgroups.all().order_by("name")

    for group in groups:
        if group.switches.count():
            switchgroups[group.name] = group
            # set this group, and the switches, in web session to track permissions
            permissions[int(group.id)] = {}
            for switch in group.switches.all():
                if switch.status == SWITCH_STATUS_ACTIVE:
                    # we save the names as well, so we can search them!
                    permissions[int(group.id)][int(switch.id)] = (
                        switch.name,
                        switch.hostname,
                        switch.description,
                        switch.default_view,
                    )

    save_to_http_session(request, "permissions", permissions)

    # log my activity
    log = Log(
        user=request.user,
        ip_address=get_remote_ip(request),
        action=LOG_VIEW_SWITCHGROUPS,
        description="Viewing switch groups",
        type=LOG_TYPE_VIEW,
    )
    log.save()

    # are there any notices to users?
    notices = Notice.objects.active_notices()
    if notices:
        for notice in notices:
            messages.add_message(
                request=request, level=notice.priority, message=notice.content
            )

    # render the template
    return render(
        request,
        template_name,
        {
            "groups": switchgroups,
            "groups_count": len(switchgroups),
        },
    )


@login_required(redirect_field_name=None)
def switch_search(request):
    """
    search for a switch by name
    """

    if not settings.SWITCH_SEARCH_FORM:
        return redirect(reverse("switches:groups"))

    search = str(request.POST.get("switchname", ""))
    # remove leading and trailing white spaceA
    search = search.strip()
    if not search:
        return redirect(reverse("switches:groups"))

    template_name = "search_results.html"

    # log my activity
    log = Log(
        user=request.user,
        ip_address=get_remote_ip(request),
        action=LOG_VIEW_SWITCH_SEARCH,
        description=f"Searching for switch '{ search }'",
        type=LOG_TYPE_VIEW,
    )
    log.save()

    results = []
    warning = False
    permissions = get_from_http_session(request, "permissions")
    if permissions and isinstance(permissions, dict):
        for group_id in permissions.keys():
            switches = permissions[group_id]
            if isinstance(switches, dict):
                for switch_id in switches.keys():
                    (name, hostname, description, default_view) = switches[switch_id]
                    # now check the name, hostname for the search pattern:
                    try:
                        if re.search(search, name, re.IGNORECASE) or re.search(
                            search, hostname, re.IGNORECASE
                        ):
                            results.append(
                                (
                                    str(group_id),
                                    str(switch_id),
                                    name,
                                    description,
                                    default_view,
                                )
                            )
                    except Exception:
                        # invalid search, just ignore!
                        warning = f"{search} - This is an invalid search pattern!"

    # render the template
    return render(
        request,
        template_name,
        {
            "warning": warning,
            "search": search,
            "results": results,
            "results_count": len(results),
        },
    )


@login_required
def switch_basics(request, group_id, switch_id):
    """
    "basic" switch view, i.e. interface data only.
    Simply call switch_view() with proper parameter
    """
    counter_increment(COUNTER_VIEWS)
    return switch_view(
        request=request, group_id=group_id, switch_id=switch_id, view="basic"
    )


@login_required(redirect_field_name=None)
def switch_arp_lldp(request, group_id, switch_id):
    """
    "details" switch view, i.e. with Ethernet/ARP/LLDP data.
    Simply call switch_view() with proper parameter
    """
    counter_increment(COUNTER_DETAILVIEWS)
    return switch_view(
        request=request, group_id=group_id, switch_id=switch_id, view="arp_lldp"
    )


@login_required(redirect_field_name=None)
def switch_hw_info(request, group_id, switch_id):
    """
    "hardware info" switch view, i.e. read detailed system hardware ("entity") data.
    Simply call switch_view() with proper parameter
    """
    counter_increment(COUNTER_HWINFO)
    return switch_view(
        request=request, group_id=group_id, switch_id=switch_id, view="hw_info"
    )


def switch_view(
    request,
    group_id,
    switch_id,
    view,
    command_id=-1,
    interface_name="",
    command_string="",
    command_template=False,
):
    """
    This shows the various data about a switch, either from a new SNMP read,
    from cached OID data, or an SSH command.
    This is includes enough to enable/disable interfaces and power,
    and change vlans. Depending on view, there may be more data needed,
    such as ethernet, arp & lldp tables.
    """

    template_name = "switch.html"

    group = get_object_or_404(SwitchGroup, pk=group_id)
    switch = get_object_or_404(Switch, pk=switch_id)

    if not rights_to_group_and_switch(request, group_id, switch_id):
        error = Error()
        error.description = "Access denied!"
        error.details = "You do not have access to this device!"
        return error_page(request=request, group=False, switch=False, error=error)

    log = Log(
        user=request.user,
        ip_address=get_remote_ip(request),
        switch=switch,
        group=group,
        action=LOG_VIEW_SWITCH,
        type=LOG_TYPE_VIEW,
        description=f"Viewing device ({view})",
    )

    try:
        conn = get_connection_object(request, group, switch)
    except Exception:
        log.type = LOG_TYPE_ERROR
        log.action = LOG_CONNECTION_ERROR
        log.description = f"CONNECTION ERROR: Viewing device ({view})"
        log.save()
        error = Error()
        error.description = "There was a failure communicating with this switch. Please contact your administrator to make sure switch data is correct in the database!"
        error.details = traceback.format_exc()
        return error_page(request=request, group=group, switch=switch, error=error)

    # catch errors in case not trapped in drivers
    try:
        if not conn.get_basic_info():
            # errors
            log.type = LOG_TYPE_ERROR
            log.description = "ERROR in get_basic_switch_info()"
            log.save()
            return error_page(
                request=request, group=group, switch=switch, error=conn.error
            )
    except Exception as e:
        log.type = LOG_TYPE_ERROR
        log.description = f"CAUGHT UNTRAPPED ERROR in get_basic_switch_info(): {repr(e)} ({str(type(e))})\n{traceback.format_exc()}"
        dprint(log.description)
        log.save()
        return error_page(request=request, group=group, switch=switch, error=conn.error)

    dprint("Basic Info OK")

    if view == "hw_info":
        # catch errors in case not trapped in drivers
        try:
            if not conn.get_hardware_details():
                # errors
                log.type = LOG_TYPE_ERROR
                log.description = "ERROR in get_hardware_details()"
                log.save()
                # don't render error, since we have already read the basic interface data
                # Note that SNMP errors are already added to warnings!
                # return error_page(request=request, group=group, switch=switch, error=conn.error)
            dprint("Details Info OK")
        except Exception as e:
            log.type = LOG_TYPE_ERROR
            log.description = f"CAUGHT UNTRAPPED ERROR in get_hardware_details(): {repr(e)} ({str(type(e))})\n{traceback.format_exc()}"
            dprint(log.description)
            log.save()
            return error_page(
                request=request, group=group, switch=switch, error=conn.error
            )

    if view == "arp_lldp":
        # catch errors in case not trapped in drivers
        try:
            if not conn.get_client_data():
                log.type = LOG_TYPE_ERROR
                log.description = "ERROR get_client_data()"
                log.save()
                # don't render error, since we have already read the basic interface data
                # Note that errors are already added to warnings!
                # return error_page(request=request, group=group, switch=switch, error=conn.error)
            dprint("ARP-LLDP Info OK")
        except Exception as e:
            log.type = LOG_TYPE_ERROR
            log.description = f"CAUGHT UNTRAPPED ERROR in get_client_data(): {repr(e)} ({str(type(e))})\n{traceback.format_exc()}"
            dprint(log.description)
            log.save()
            return error_page(
                request=request, group=group, switch=switch, error=conn.error
            )

    # done with reading switch data, so save cachable/session data
    conn.save_cache()

    # does this switch have any commands defined?
    cmd = False
    # check that we can process commands, and have valid commands assigned to switch
    if command_id > -1:
        # Exexute a specific Command object by ID, note rights are checked in run_command()!
        dprint("CALLING RUN_COMMAND()")
        counter_increment(COUNTER_COMMANDS)
        cmd = conn.run_command(command_id=command_id, interface_name=interface_name)
        if conn.error.status:
            # log it!
            log.type = LOG_TYPE_ERROR
            log.action = LOG_EXECUTE_COMMAND
            log.description = f"{cmd['error_descr']}: {cmd['error_details']}"
        else:
            # success !
            log.type = LOG_TYPE_COMMAND
            log.action = LOG_EXECUTE_COMMAND
            log.description = cmd["command"]
        log.save()
    elif command_string:
        dprint("CALLING RUN_COMMAND_STRING")
        counter_increment(COUNTER_COMMANDS)
        cmd = conn.run_command_string(command_string=command_string)
        dprint(f"OUTPUT = {cmd}")
        if conn.error.status:
            # log it!
            log.type = LOG_TYPE_ERROR
            log.action = LOG_EXECUTE_COMMAND
            log.description = f"{cmd['error_descr']}: {cmd['error_details']}"
            log.save()
        else:
            # success !
            log.type = LOG_TYPE_COMMAND
            log.action = LOG_EXECUTE_COMMAND
            log.description = cmd["command"]
            log.save()
            # if the result of a command template, we may need to parse the output:
            if command_template:
                # do we need to match output to show match/fail result?
                output = cmd["output"]
                if command_template.output_match_regex:
                    if string_contains_regex(
                        cmd["output"], command_template.output_match_regex
                    ):
                        cmd["output"] = (
                            command_template.output_match_text
                            if command_template.output_match_text
                            else "OK!"
                        )
                    else:
                        cmd["output"] = (
                            command_template.output_fail_text
                            if command_template.output_fail_text
                            else "FAIL!"
                        )
                # do we need to filter (original) output to keep only matching lines?
                if command_template.output_lines_keep_regex:
                    matched_lines = ""
                    lines = output.splitlines()
                    for line in lines:
                        # we can probably improve performance by compiling the regex first...
                        if string_contains_regex(
                            line, command_template.output_lines_keep_regex
                        ):
                            matched_lines = f"{matched_lines}\n{line}"
                    if matched_lines:
                        cmd["output"] += "\nPartial output:\n" + matched_lines

    else:
        # log the access:
        log.save()

    # get recent "non-viewing" activity for this switch
    # for now, show most recent 25 activities
    logs = (
        Log.objects.all()
        .filter(switch=switch, type__gt=LOG_TYPE_VIEW)
        .order_by("-timestamp")[: settings.RECENT_SWITCH_LOG_COUNT]
    )

    time_since_last_read = time_duration(time.time() - conn.basic_info_read_timestamp)

    # finally, verify what this user can do:
    bulk_edit = len(conn.interfaces) and user_can_bulkedit(request.user, group, switch)
    edit_vlans = (
        conn.can_edit_vlans
        and len(conn.interfaces)
        and user_can_edit_vlans(request.user, group, switch)
    )

    log_title = "Recent Activity"

    return render(
        request,
        template_name,
        {
            "group": group,
            "switch": switch,
            "connection": conn,
            "logs": logs,
            "log_title": log_title,
            "logs_link": True,
            "view": view,
            "cmd": cmd,
            "bulk_edit": bulk_edit,
            "edit_vlans": edit_vlans,
            "time_since_last_read": time_since_last_read,
        },
    )


#
# Bulk Edit interfaces on a switch
#
@login_required(redirect_field_name=None)
def switch_bulkedit(request, group_id, switch_id):
    """
    Change several interfaces at once.
    """
    group = get_object_or_404(SwitchGroup, pk=group_id)
    switch = get_object_or_404(Switch, pk=switch_id)

    if not rights_to_group_and_switch(request, group_id, switch_id):
        error = Error()
        error.description = "Access denied!"
        error.details = "You do not have access to this device!"
        counter_increment(COUNTER_ACCESS_DENIED)
        return error_page(request=request, group=False, switch=False, error=error)

    counter_increment(COUNTER_BULKEDITS)

    remote_ip = get_remote_ip(request)

    try:
        conn = get_connection_object(request, group, switch)
    except Exception:
        log = Log(
            user=request.user,
            ip_address=remote_ip,
            switch=switch,
            group=group,
            action=LOG_CONNECTION_ERROR,
            type=LOG_TYPE_ERROR,
            description="Could not get connection",
        )
        log.save()
        error = Error()
        error.description = "Could not get connection. Please contact your administrator to make sure switch data is correct in the database!"
        error.details = (
            "This is likely a configuration error, such as wrong SNMP settings."
        )
        return error_page(request=request, group=group, switch=switch, error=error)

    # read the submitted form data:
    interface_change = int(request.POST.get("interface_change", INTERFACE_STATUS_NONE))
    poe_choice = int(request.POST.get("poe_choice", BULKEDIT_POE_NONE))
    new_pvid = int(request.POST.get("new_pvid", -1))
    new_description = str(request.POST.get("new_description", ""))
    new_description_type = int(
        request.POST.get("new_description_type", BULKEDIT_ALIAS_TYPE_REPLACE)
    )
    interface_list = request.POST.getlist("interface_list")

    # was anything submitted?
    if len(interface_list) == 0:
        return warning_page(
            request=request,
            group=group,
            switch=switch,
            description=mark_safe("Please select at least 1 interface!"),
        )

    if (
        interface_change == INTERFACE_STATUS_NONE
        and poe_choice == BULKEDIT_POE_NONE
        and new_pvid < 0
        and not new_description
    ):
        return warning_page(
            request=request,
            group=group,
            switch=switch,
            description=mark_safe("Please select at least 1 thing to change!"),
        )

    # perform some checks on valid data first:
    errors = []

    # check if the new description/description is allowed:
    if (
        new_description
        and new_description_type == BULKEDIT_ALIAS_TYPE_REPLACE
        and settings.IFACE_ALIAS_NOT_ALLOW_REGEX
    ):
        match = re.match(settings.IFACE_ALIAS_NOT_ALLOW_REGEX, new_description)
        if match:
            log = Log(
                user=request.user,
                ip_address=remote_ip,
                switch=switch,
                group=group,
                type=LOG_TYPE_ERROR,
                action=LOG_CHANGE_BULK_EDIT,
                description=f"Description not allowed: {new_description}",
            )
            log.save()
            new_description = ""
            counter_increment(COUNTER_ERRORS)
            errors.append(f"The description is not allowed: {new_description}")

    # safety-check: is the new PVID allowed:
    if new_pvid > 0:
        conn._set_allowed_vlans()
        if new_pvid not in conn.allowed_vlans.keys():
            log = Log(
                user=request.user,
                ip_address=remote_ip,
                switch=switch,
                group=group,
                type=LOG_TYPE_ERROR,
                action=LOG_CHANGE_BULK_EDIT,
                description=f"New vlan '{new_pvid}' is not allowed!",
            )
            log.save()
            new_pvid = -1  # force no change!
            errors.append(f"New vlan '{new_pvid}' is not allowed!")
            counter_increment(COUNTER_ERRORS)

    if len(errors) > 0:
        error = Error()
        error.description = (
            "Some form values were invalid, please correct and resubmit!"
        )
        error.details = mark_safe("\n<br>".join(errors))
        return error_page(request=request, group=group, switch=switch, error=error)

    # get the name of the interfaces as well (with the submitted if_key values)
    # so that we can show the names in the Log() objects
    # additionally, also get the current state, to be able to "undo" the update
    interfaces = {}  # dict() of interfaces to bulk edit
    undo_info = {}
    for if_key in interface_list:
        dprint(f"BulkEdit for {if_key}")
        interface = conn.get_interface_by_key(if_key)
        if interface:
            interfaces[if_key] = interface.name

    # handle regular submit, execute now!
    results = bulkedit_processor(
        request,
        group,
        switch,
        interface_change,
        poe_choice,
        new_pvid,
        new_description,
        new_description_type,
        interfaces,
    )

    # indicate we need to save config!
    if results["success_count"] > 0:
        conn.set_save_needed(True)
        # and save data in session
        conn.save_cache()

    # now build the results page from the outputs
    result_str = "\n<br>".join(results["outputs"])
    description = f"\n<div><strong>Bulk-Edit Results:</strong></div>\n<br>{result_str}"
    if results["error_count"] > 0:
        err = Error()
        err.description = "Bulk-Edit errors"
        err.details = mark_safe(description)
        return error_page(request=request, group=group, switch=switch, error=err)
    else:
        return success_page(request, group, switch, mark_safe(description))


def bulkedit_processor(
    request,
    group,
    switch,
    interface_change,
    poe_choice,
    new_pvid,
    new_description,
    new_description_type,
    interfaces,
):
    """
    Function to handle the bulk edit processing, from form-submission or scheduled job.
    This will log each individual action per interface.
    Returns the number of successful action, number of error actions, and
    a list of outputs with text information about each action.
    """

    remote_ip = get_remote_ip(request)

    # log bulk edit arguments:
    log = Log(
        user=request.user,
        switch=switch,
        group=group,
        ip_address=remote_ip,
        action=LOG_BULK_EDIT_TASK_START,
        description=f"Interface Status={get_choice_name(BULKEDIT_INTERFACE_CHOICES, interface_change)}, "
        f"PoE Status={get_choice_name(BULKEDIT_POE_CHOICES, poe_choice)}, "
        f"Vlan={new_pvid}, "
        f"Descr Type={get_choice_name(BULKEDIT_ALIAS_TYPE_CHOICES, new_description_type)}, "
        f"Descr={new_description}",
        type=LOG_TYPE_CHANGE,
    )
    log.save()

    # this needs work:
    conn = get_connection_object(request, group, switch)
    if not request:
        # running asynchronously (as task), we need to read the device
        # to get access to interfaces.
        conn.get_basic_info()

    # now do the work, and log each change
    runtime_undo_info = {}
    iface_count = 0
    success_count = 0
    error_count = 0
    outputs = []  # description of any errors found
    for if_key, name in interfaces.items():
        iface = conn.get_interface_by_key(if_key)
        if not iface:
            error_count += 1
            outputs.append(f"ERROR: interface for index '{if_key}' not found!")
            continue
        iface_count += 1

        # save the current state, right before we make a change!
        current_state = {"if_key": if_key, "name": iface.name}

        # now check all the things we could be changing,
        # start with UP/DOWN state:
        if interface_change != INTERFACE_STATUS_NONE:
            log = Log(
                user=request.user,
                ip_address=remote_ip,
                if_name=iface.name,
                switch=switch,
                group=group,
            )
            current_state["admin_state"] = iface.admin_status
            if interface_change == INTERFACE_STATUS_CHANGE:
                if iface.admin_status:
                    new_state = False
                    new_state_name = "Down"
                    log.action = LOG_CHANGE_INTERFACE_DOWN
                else:
                    new_state = True
                    new_state_name = "Up"
                    log.action = LOG_CHANGE_INTERFACE_UP

            elif interface_change == INTERFACE_STATUS_DOWN:
                new_state = False
                new_state_name = "Down"
                log.action = LOG_CHANGE_INTERFACE_DOWN

            elif interface_change == INTERFACE_STATUS_UP:
                new_state = True
                new_state_name = "Up"
                log.action = LOG_CHANGE_INTERFACE_UP

            # are we actually making a change?
            if new_state != current_state["admin_state"]:
                # yes, apply the change:
                retval = conn.set_interface_admin_status(iface, new_state)
                if retval:
                    success_count += 1
                    log.type = LOG_TYPE_CHANGE
                    log.description = (
                        f"Interface {iface.name}: Admin set to {new_state_name}"
                    )
                    counter_increment(COUNTER_CHANGES)
                else:
                    error_count += 1
                    log.type = LOG_TYPE_ERROR
                    log.description = f"Interface {iface.name}: Admin {new_state_name} ERROR: {conn.error.description}"
                    counter_increment(COUNTER_ERRORS)
            else:
                # already in wanted admin state:
                log.type = LOG_TYPE_CHANGE
                log.description = (
                    f"Interface {iface.name}: Ignored - already {new_state_name}"
                )
            outputs.append(log.description)
            log.save()

        # next work on PoE state:
        if poe_choice != BULKEDIT_POE_NONE:
            if not iface.poe_entry:
                outputs.append(f"Interface {iface.name}: Ignored - not PoE capable")
            else:
                log = Log(
                    user=request.user,
                    ip_address=remote_ip,
                    if_name=iface.name,
                    switch=switch,
                    group=group,
                )
                current_state["poe_state"] = iface.poe_entry.admin_status
                if poe_choice == BULKEDIT_POE_DOWN_UP:
                    # Down / Up on interfaces with PoE Enabled:
                    if iface.poe_entry.admin_status == POE_PORT_ADMIN_ENABLED:
                        log.action = LOG_CHANGE_INTERFACE_POE_TOGGLE_DOWN_UP
                        # the PoE index is kept in the iface.poe_entry
                        # First disable PoE. Make sure we cast the proper type here! Ie this needs an Integer()
                        # retval = conn.set(f"{pethPsePortAdminEnable}.{iface.poe_entry.index}", POE_PORT_ADMIN_DISABLED, 'i')
                        # First disable PoE
                        retval = conn.set_interface_poe_status(
                            iface, POE_PORT_ADMIN_DISABLED
                        )
                        if retval < 0:
                            log.description = f"ERROR: Toggle-Disable PoE on interface {iface.name} - {conn.error.description}"
                            log.type = LOG_TYPE_ERROR
                            outputs.append(log.description)
                            log.save()
                            counter_increment(COUNTER_ERRORS)
                        else:
                            # successful power down
                            counter_increment(COUNTER_CHANGES)
                            # now delay
                            time.sleep(settings.POE_TOGGLE_DELAY)
                            # Now enable PoE again...
                            # retval = conn.set(f"{pethPsePortAdminEnable}.{iface.poe_entry.index}", POE_PORT_ADMIN_ENABLED, 'i')
                            retval = conn.set_interface_poe_status(
                                iface, POE_PORT_ADMIN_ENABLED
                            )
                            if retval < 0:
                                log.description = f"ERROR: Toggle-Enable PoE on interface {iface.name} - {conn.error.description}"
                                log.type = LOG_TYPE_ERROR
                                outputs.append(log.description)
                                log.save()
                                counter_increment(COUNTER_ERRORS)
                            else:
                                # all went well!
                                success_count += 1
                                log.type = LOG_TYPE_CHANGE
                                log.description = (
                                    f"Interface {iface.name}: PoE Toggle Down/Up OK"
                                )
                                outputs.append(log.description)
                                log.save()
                                counter_increment(COUNTER_CHANGES)
                    else:
                        outputs.append(
                            f"Interface {iface.name}: PoE Down/Up IGNORED, PoE NOT enabled"
                        )

                else:
                    # just enable or disable:
                    if poe_choice == BULKEDIT_POE_CHANGE:
                        # the PoE index is kept in the iface.poe_entry
                        if iface.poe_entry.admin_status == POE_PORT_ADMIN_ENABLED:
                            new_state = POE_PORT_ADMIN_DISABLED
                            new_state_name = "Disabled"
                            log.action = LOG_CHANGE_INTERFACE_POE_DOWN
                        else:
                            new_state = POE_PORT_ADMIN_ENABLED
                            new_state_name = "Enabled"
                            log.action = LOG_CHANGE_INTERFACE_POE_UP

                    elif poe_choice == BULKEDIT_POE_DOWN:
                        new_state = POE_PORT_ADMIN_DISABLED
                        new_state_name = "Disabled"
                        log.action = LOG_CHANGE_INTERFACE_POE_DOWN

                    elif poe_choice == BULKEDIT_POE_UP:
                        new_state = POE_PORT_ADMIN_ENABLED
                        new_state_name = "Enabled"
                        log.action = LOG_CHANGE_INTERFACE_POE_UP

                    # are we actually making a change?
                    if new_state != current_state["poe_state"]:
                        # yes, go do it:
                        retval = conn.set_interface_poe_status(iface, new_state)
                        if retval < 0:
                            error_count += 1
                            log.type = LOG_TYPE_ERROR
                            log.description = f"Interface {iface.name}: PoE {new_state_name} ERROR: {conn.error.description}"
                            outputs.append(log.description)
                            log.save()
                            counter_increment(COUNTER_ERRORS)
                        else:
                            success_count += 1
                            log.type = LOG_TYPE_CHANGE
                            log.description = (
                                f"Interface {iface.name}: PoE {new_state_name}"
                            )
                            outputs.append(log.description)
                            log.save()
                            counter_increment(COUNTER_CHANGES)
                    else:
                        # already in wanted power state:
                        outputs.append(
                            f"Interface {iface.name}: Ignored, PoE already {new_state_name}"
                        )

        # do we want to change the untagged vlan:
        if new_pvid > 0:
            if iface.lacp_master_index > 0:
                # LACP member interface, we cannot edit the vlan!
                log = Log(
                    user=request.user,
                    ip_address=remote_ip,
                    if_name=iface.name,
                    switch=switch,
                    group=group,
                    type=LOG_TYPE_WARNING,
                    action=LOG_CHANGE_INTERFACE_PVID,
                    description=f"Interface {iface.name}: LACP Member, Vlan set to {new_pvid} IGNORED!",
                )
                outputs.append(log.description)
                log.save()
            else:
                # make sure we cast the proper type here! Ie this needs an Integer()
                log = Log(
                    user=request.user,
                    ip_address=remote_ip,
                    if_name=iface.name,
                    switch=switch,
                    group=group,
                    action=LOG_CHANGE_INTERFACE_PVID,
                )
                current_state["pvid"] = iface.untagged_vlan
                if new_pvid != iface.untagged_vlan:
                    # new vlan, go set it:
                    retval = conn.set_interface_untagged_vlan(iface, new_pvid)
                    if retval < 0:
                        error_count += 1
                        log.type = LOG_TYPE_ERROR
                        log.description = f"Interface {iface.name}: Vlan change ERROR: {conn.error.description}"
                        counter_increment(COUNTER_ERRORS)
                    else:
                        success_count += 1
                        log.type = LOG_TYPE_CHANGE
                        log.description = (
                            f"Interface {iface.name}: Vlan set to {new_pvid}"
                        )
                    outputs.append(log.description)
                    log.save()
                    counter_increment(COUNTER_CHANGES)
                else:
                    # already on desired vlan:
                    outputs.append(
                        f"Interface {iface.name}: Ignored, VLAN already {new_pvid}"
                    )

        # tired of the old interface description?
        if new_description:
            iface_new_description = ""
            # what are we supposed to do with the description/description?
            if new_description_type == BULKEDIT_ALIAS_TYPE_APPEND:
                iface_new_description = f"{iface.description} {new_description}"
                # outputs.append(f"Interface {iface.name}: Description Append: {iface_new_description}")
            elif new_description_type == BULKEDIT_ALIAS_TYPE_REPLACE:
                # check if the original description starts with a string we have to keep:
                if settings.IFACE_ALIAS_KEEP_BEGINNING_REGEX:
                    keep_format = f"(^{settings.IFACE_ALIAS_KEEP_BEGINNING_REGEX})"
                    match = re.match(keep_format, iface.description)
                    if match:
                        # beginning match, but check if new submitted description matches requirement:
                        match_new = re.match(keep_format, new_description)
                        if not match_new:
                            # required start string NOT found on new description, so prepend it!
                            iface_new_description = f"{match[1]} {new_description}"
                        else:
                            # new description matches beginning format, keep as is:
                            iface_new_description = new_description
                    else:
                        # no beginning match, just set new description:
                        iface_new_description = new_description
                else:
                    # nothing special, just set new description:
                    iface_new_description = new_description

            # elif new_description_type == BULKEDIT_ALIAS_TYPE_PREPEND:
            # To be implemented

            log = Log(
                user=request.user,
                ip_address=remote_ip,
                if_name=iface.name,
                switch=switch,
                group=group,
                action=LOG_CHANGE_INTERFACE_ALIAS,
            )
            current_state["description"] = iface.description
            retval = conn.set_interface_description(iface, iface_new_description)
            if retval < 0:
                error_count += 1
                log.type = LOG_TYPE_ERROR
                log.description = (
                    f"Interface {iface.name}: Descr ERROR: {conn.error.description}"
                )
                log.save()
                counter_increment(COUNTER_ERRORS)
                return error_page(request, group, switch, conn.error)
            else:
                success_count += 1
                log.type = LOG_TYPE_CHANGE
                log.description = f"Interface {iface.name}: Descr set OK"
                counter_increment(COUNTER_CHANGES)
            outputs.append(log.description)
            log.save()

        # done with this interface, add pre-change state!
        runtime_undo_info[if_key] = current_state

    # log final results
    log = Log(
        user=request.user,
        ip_address=remote_ip,
        switch=switch,
        group=group,
        type=LOG_TYPE_CHANGE,
        action=LOG_CHANGE_BULK_EDIT,
    )
    if error_count > 0:
        log.type = LOG_TYPE_ERROR
        log.description = "Bulk Edits had errors! (see previous entries)"
    else:
        log.description = "Bulk Edits OK!"
    log.save()

    results = {
        "success_count": success_count,
        "error_count": error_count,
        "outputs": outputs,
    }
    return results


#
# Manage vlans on a device
#
@login_required(redirect_field_name=None)
def switch_vlan_manage(request, group_id, switch_id):
    """
    Manage vlan to a device. Form data will be POST-ed.
    """
    group = get_object_or_404(SwitchGroup, pk=group_id)
    switch = get_object_or_404(Switch, pk=switch_id)

    if not rights_to_group_and_switch(request, group_id, switch_id):
        error = Error()
        error.description = "Access denied!"
        error.details = "You do not have access to this device!"
        counter_increment(COUNTER_ACCESS_DENIED)
        return error_page(request=request, group=False, switch=False, error=error)

    remote_ip = get_remote_ip(request)

    try:
        conn = get_connection_object(request, group, switch)
    except Exception:
        log = Log(
            user=request.user,
            ip_address=remote_ip,
            switch=switch,
            group=group,
            action=LOG_CONNECTION_ERROR,
            type=LOG_TYPE_ERROR,
            description="Could not get connection",
        )
        log.save()
        error = Error()
        error.description = "Could not get connection. Please contact your administrator to make sure switch data is correct in the database!"
        error.details = (
            "This is likely a configuration error, such as wrong SNMP settings."
        )
        return error_page(request=request, group=group, switch=switch, error=error)

    # parse form items:
    vlan_id = int(request.POST.get("vlan_id", -1))
    vlan_name = str(request.POST.get("vlan_name", "")).strip()

    if request.POST.get("vlan_create"):
        if vlan_id > 1 and vlan_id < 4095 and vlan_name:
            # all OK, go create
            counter_increment(COUNTER_VLAN_MANAGE)
            status = conn.vlan_create(vlan_id=vlan_id, vlan_name=vlan_name)
            if status:
                log = Log(
                    user=request.user,
                    ip_address=remote_ip,
                    switch=switch,
                    group=group,
                    action=LOG_VLAN_CREATE,
                    type=LOG_TYPE_CHANGE,
                    description=f"VLAN {vlan_id} ({vlan_name}) created.",
                )
                log.save()
                # need to save changes
                conn.set_save_needed(True)
                # and save data in session
                conn.save_cache()
                return success_page(
                    request=request,
                    group=group,
                    switch=switch,
                    description="New vlan created successfully!",
                )
            else:
                error = Error()
                error.status = True
                error.description = "Error creating new vlan!"
                error.details = conn.error.details
                log = Log(
                    user=request.user,
                    ip_address=remote_ip,
                    switch=switch,
                    group=group,
                    action=LOG_VLAN_CREATE,
                    type=LOG_TYPE_ERROR,
                    description=f"Error creating VLAN {vlan_id} ({vlan_name}): {conn.error.details}",
                )
                log.save()
                return error_page(
                    request=request, group=group, switch=switch, error=error
                )
        else:
            error = Error()
            error.status = True
            error.description = "Invalid new vlan data (id or name), please try again!"
            return error_page(request=request, group=group, switch=switch, error=error)

    elif request.POST.get("vlan_edit"):
        if vlan_id > 1 and vlan_id < 4095 and vlan_name:
            status = conn.vlan_edit(vlan_id=vlan_id, vlan_name=vlan_name)
            if status:
                log = Log(
                    user=request.user,
                    ip_address=remote_ip,
                    switch=switch,
                    group=group,
                    action=LOG_VLAN_EDIT,
                    type=LOG_TYPE_CHANGE,
                    description=f"VLAN {vlan_id} renamed to '{vlan_name}'",
                )
                log.save()
                # need to save changes
                conn.set_save_needed(True)
                # and save data in session
                conn.save_cache()
                counter_increment(COUNTER_VLAN_MANAGE)
                return success_page(
                    request=request,
                    group=group,
                    switch=switch,
                    description=f"Updated name for vlan {vlan_id} to '{vlan_name}'",
                )
            else:
                error = Error()
                error.status = True
                error.description = "Error updating new vlan!"
                error.details = conn.error.details
                log = Log(
                    user=request.user,
                    ip_address=remote_ip,
                    switch=switch,
                    group=group,
                    action=LOG_VLAN_EDIT,
                    type=LOG_TYPE_ERROR,
                    description=f"Error updating VLAN {vlan_id} name to '{vlan_name}': {conn.error.details}",
                )
                log.save()
                return error_page(
                    request=request, group=group, switch=switch, error=error
                )
        else:
            error = Error()
            error.status = True
            error.description = "Invalid data to update vlan, please try again!"
            return error_page(request=request, group=group, switch=switch, error=error)

    elif request.POST.get("vlan_delete"):
        if request.user.is_superuser:
            status = conn.vlan_delete(vlan_id=vlan_id)
            if status:
                log = Log(
                    user=request.user,
                    ip_address=remote_ip,
                    switch=switch,
                    group=group,
                    action=LOG_VLAN_DELETE,
                    type=LOG_TYPE_CHANGE,
                    description=f"VLAN {vlan_id} deleted.",
                )
                log.save()
                # need to save changes
                conn.set_save_needed(True)
                # and save data in session
                conn.save_cache()
                counter_increment(COUNTER_VLAN_MANAGE)
                return success_page(
                    request=request,
                    group=group,
                    switch=switch,
                    description=f"Vlan {vlan_id} was deleted!",
                )
            else:
                error = Error()
                error.status = True
                error.description = "Error deleting vlan!"
                error.details = conn.error.details
                log = Log(
                    user=request.user,
                    ip_address=remote_ip,
                    switch=switch,
                    group=group,
                    action=LOG_VLAN_DELETE,
                    type=LOG_TYPE_ERROR,
                    description=f"Error deleting VLAN {vlan_id}: {conn.error.details}",
                )
                log.save()
                return error_page(
                    request=request, group=group, switch=switch, error=error
                )
        else:
            # NOT allowed if you are not super user!
            error = Error()
            error.status = True
            error.description = (
                "Access Denied: you need to be SuperUser to delete a VLAN"
            )
            return error_page(request=request, group=group, switch=switch, error=error)

    error = Error()
    error.status = True
    error.description = (
        f"UNKNOWN Vlan Management action: POST={dict(request.POST.items())}"
    )
    return error_page(request=request, group=group, switch=switch, error=error)


#
# Change admin status, ie port Enable/Disable
#
@login_required(redirect_field_name=None)
def interface_admin_change(request, group_id, switch_id, interface_name, new_state):
    """
    Toggle the admin status of an interface, ie admin up or down.
    """
    group = get_object_or_404(SwitchGroup, pk=group_id)
    switch = get_object_or_404(Switch, pk=switch_id)

    if not rights_to_group_and_switch(request, group_id, switch_id):
        error = Error()
        error.description = "Access denied!"
        error.details = "You do not have access to this device!"
        counter_increment(COUNTER_ERRORS)
        return error_page(request=request, group=False, switch=False, error=error)

    log = Log(
        user=request.user,
        ip_address=get_remote_ip(request),
        switch=switch,
        group=group,
        if_name=interface_name,
    )

    try:
        conn = get_connection_object(request, group, switch)
    except Exception:
        log.type = LOG_TYPE_ERROR
        log.action = LOG_CONNECTION_ERROR
        log.description = "Could not get connection"
        log.save()
        counter_increment(COUNTER_ERRORS)
        error = Error()
        error.description = "Could not get connection. Please contact your administrator to make sure switch data is correct in the database!"
        error.details = (
            "This is likely a configuration error, such as incorrect SNMP settings."
        )
        return error_page(request=request, group=group, switch=switch, error=error)

    interface = conn.get_interface_by_key(interface_name)
    if not interface:
        log.type = LOG_TYPE_ERROR
        log.description = (
            f"Admin-Change: Error getting interface data for {interface_name}"
        )
        log.save()
        counter_increment(COUNTER_ERRORS)
        error = Error()
        error.description = (
            "Could not get interface data. Please contact your administrator!"
        )
        error.details = "Sorry, no more details available!"
        return error_page(request=request, group=group, switch=switch, error=error)

    log.type = LOG_TYPE_CHANGE
    if new_state:
        log.action = LOG_CHANGE_INTERFACE_UP
        log.description = f"Interface {interface.name}: Enabled"
        state = "Enabled"
    else:
        log.action = LOG_CHANGE_INTERFACE_DOWN
        log.description = f"Interface {interface.name}: Disabled"
        state = "Disabled"

    if not conn.set_interface_admin_status(interface, bool(new_state)):
        log.description = f"ERROR: {conn.error.description}"
        log.type = LOG_TYPE_ERROR
        log.save()
        counter_increment(COUNTER_ERRORS)
        return error_page(request=request, group=group, switch=switch, error=conn.error)

    # indicate we need to save config!
    conn.set_save_needed(True)

    # and save data in session
    conn.save_cache()

    log.save()
    counter_increment(COUNTER_CHANGES)

    description = f"Interface {interface.name} is now {state}"
    return success_page(request, group, switch, description)


@login_required(redirect_field_name=None)
def interface_description_change(request, group_id, switch_id, interface_name):
    """
    Change the ifAlias aka description on an interfaces.
    """
    group = get_object_or_404(SwitchGroup, pk=group_id)
    switch = get_object_or_404(Switch, pk=switch_id)

    if not rights_to_group_and_switch(request, group_id, switch_id):
        error = Error()
        error.description = "Access denied!"
        error.details = "You do not have access to this device!"
        counter_increment(COUNTER_ERRORS)
        return error_page(request=request, group=False, switch=False, error=error)

    log = Log(
        user=request.user,
        ip_address=get_remote_ip(request),
        switch=switch,
        group=group,
        action=LOG_CHANGE_INTERFACE_ALIAS,
        if_name=interface_name,
    )

    try:
        conn = get_connection_object(request, group, switch)
    except Exception:
        log.type = LOG_TYPE_ERROR
        log.action = LOG_CONNECTION_ERROR
        log.description = "Could not get connection"
        log.save()
        counter_increment(COUNTER_ERRORS)
        error = Error()
        error.description = "Could not get connection. Please contact your administrator to make sure switch data is correct in the database!"
        error.details = (
            "This is likely a configuration error, such as incorrect SNMP settings!"
        )
        return error_page(request=request, group=group, switch=switch, error=error)

    interface = conn.get_interface_by_key(interface_name)
    if not interface:
        log.type = LOG_TYPE_ERROR
        log.description = (
            f"Alias-Change: Error getting interface data for {interface_name}"
        )
        log.save()
        counter_increment(COUNTER_ERRORS)
        error = Error()
        error.description = (
            "Could not get interface data. Please contact your administrator!"
        )
        error.details = "Sorry, no more details available!"
        return error_page(request=request, group=group, switch=switch, error=error)

    # read the submitted form data:
    new_description = str(request.POST.get("new_description", ""))

    if interface.description == new_description:
        description = "New description is the same, please change it first!"
        return warning_page(
            request=request, group=group, switch=switch, description=description
        )

    log.type = LOG_TYPE_CHANGE

    # are we allowed to change description ?
    if not interface.can_edit_description:
        log.description = f"Interface {interface.name} description edit not allowed"
        log.type = LOG_TYPE_ERROR
        log.save()
        counter_increment(COUNTER_ERRORS)
        error = Error()
        error.description = "You are not allowed to change the interface description"
        error.details = "Sorry, you do not have access!"
        return error_page(request=request, group=group, switch=switch, error=error)

    # check if the description is allowed:
    if settings.IFACE_ALIAS_NOT_ALLOW_REGEX:
        match = re.match(settings.IFACE_ALIAS_NOT_ALLOW_REGEX, new_description)
        if match:
            log.type = LOG_TYPE_ERROR
            log.description = "New description matches admin deny setting!"
            log.save()
            counter_increment(COUNTER_ERRORS)
            error = Error()
            error.description = f"The description '{new_description}' is not allowed!"
            return error_page(request=request, group=group, switch=switch, error=error)

    # check if the original description starts with a string we have to keep
    if settings.IFACE_ALIAS_KEEP_BEGINNING_REGEX:
        keep_format = f"(^{settings.IFACE_ALIAS_KEEP_BEGINNING_REGEX})"
        match = re.match(keep_format, interface.description)
        if match:
            # check of new submitted description begins with this string:
            match_new = re.match(keep_format, new_description)
            if not match_new:
                # required start string NOT found on new description, so prepend it!
                new_description = f"{match[1]} {new_description}"

    # log the work!
    log.description = f"Interface {interface.name}: Description = {new_description}"
    # and do the work:
    if not conn.set_interface_description(interface, new_description):
        log.description = f"ERROR: {conn.error.description}"
        log.type = LOG_TYPE_ERROR
        log.save()
        counter_increment(COUNTER_ERRORS)
        return error_page(request=request, group=group, switch=switch, error=conn.error)

    # indicate we need to save config!
    conn.set_save_needed(True)

    # and save cachable/session data
    conn.save_cache()

    log.save()
    counter_increment(COUNTER_CHANGES)

    description = f"Interface {interface.name} description changed"
    return success_page(request, group, switch, description)


@login_required(redirect_field_name=None)
def interface_pvid_change(request, group_id, switch_id, interface_name):
    """
    Change the PVID untagged vlan on an interfaces.
    This still needs to handle dot1q trunked ports.
    """
    group = get_object_or_404(SwitchGroup, pk=group_id)
    switch = get_object_or_404(Switch, pk=switch_id)

    if not rights_to_group_and_switch(request, group_id, switch_id):
        error = Error()
        error.description = "Access denied!"
        counter_increment(COUNTER_ACCESS_DENIED)
        return error_page(request=request, group=False, switch=False, error=error)

    log = Log(
        user=request.user,
        ip_address=get_remote_ip(request),
        switch=switch,
        group=group,
        action=LOG_CHANGE_INTERFACE_PVID,
        if_name=interface_name,
    )

    try:
        conn = get_connection_object(request, group, switch)
    except Exception:
        log.type = LOG_TYPE_ERROR
        log.action = LOG_CONNECTION_ERROR
        log.description = "Could not get connection"
        log.save()
        counter_increment(COUNTER_ERRORS)
        error = Error()
        error.description = "Could not get connection. Please contact your administrator to make sure switch data is correct in the database!"
        return error_page(request=request, group=group, switch=switch, error=error)

    interface = conn.get_interface_by_key(interface_name)
    if not interface:
        log.type = LOG_TYPE_ERROR
        log.description = (
            f"Pvid-Change: Error getting interface data for {interface_name}"
        )
        log.save()
        counter_increment(COUNTER_ERRORS)
        error = Error()
        error.description = (
            "Could not get interface data. Please contact your administrator!"
        )
        return error_page(request=request, group=group, switch=switch, error=error)

    # read the submitted form data:
    new_pvid = int(request.POST.get("new_pvid", 0))
    # did the vlan change?
    if interface.untagged_vlan == int(new_pvid):
        description = f"New vlan {interface.untagged_vlan} is the same, please change the vlan first!"
        return warning_page(
            request=request, group=group, switch=switch, description=description
        )

    log.type = LOG_TYPE_CHANGE
    log.description = f"Interface {interface.name}: new PVID = {new_pvid} (was {interface.untagged_vlan})"

    # are we allowed to change to this vlan ?
    conn._set_allowed_vlans()
    if not int(new_pvid) in conn.allowed_vlans.keys():
        log.type = LOG_TYPE_ERROR
        log.save()
        counter_increment(COUNTER_ERRORS)
        error = Error()
        error.status = True
        error.description = (
            f"New vlan {new_pvid} is not valid or allowed on this device"
        )
        return error_page(request=request, group=group, switch=switch, error=error)

    # make sure we cast the proper type here! Ie this needs an Integer()
    if not conn.set_interface_untagged_vlan(interface, int(new_pvid)):
        log.description = f"ERROR: {conn.error.description}"
        log.type = LOG_TYPE_ERROR
        log.save()
        counter_increment(COUNTER_ERRORS)
        return error_page(request=request, group=group, switch=switch, error=conn.error)

    # indicate we need to save config!
    conn.set_save_needed(True)

    # and save cachable/session data
    conn.save_cache()

    # all OK, save log
    log.save()
    counter_increment(COUNTER_CHANGES)

    description = f"Interface {interface.name} changed to vlan {new_pvid}"
    return success_page(request, group, switch, description)


#
# Change PoE status, i.e. port power Enable/Disable
#
@login_required(redirect_field_name=None)
def interface_poe_change(request, group_id, switch_id, interface_name, new_state):
    """
    Change the PoE status of an interfaces.
    This still needs to be tested for propper PoE port to interface ifIndex mappings.
    """
    group = get_object_or_404(SwitchGroup, pk=group_id)
    switch = get_object_or_404(Switch, pk=switch_id)

    if not rights_to_group_and_switch(request, group_id, switch_id):
        error = Error()
        error.status = True
        error.description = "Access denied!"
        counter_increment(COUNTER_ACCESS_DENIED)
        return error_page(request=request, group=False, switch=False, error=error)

    log = Log(
        user=request.user,
        ip_address=get_remote_ip(request),
        switch=switch,
        group=group,
        if_name=interface_name,
    )

    try:
        conn = get_connection_object(request, group, switch)
    except Exception:
        log.type = LOG_TYPE_ERROR
        log.action = LOG_CONNECTION_ERROR
        log.description = "Could not get connection"
        log.save()
        counter_increment(COUNTER_ERRORS)
        error = Error()
        error.description = "Could not get connection. Please contact your administrator to make sure switch data is correct in the database!"
        return error_page(request=request, group=group, switch=switch, error=error)

    interface = conn.get_interface_by_key(interface_name)
    if not interface:
        log.type = LOG_TYPE_ERROR
        log.description = (
            f"PoE-Change: Error getting interface data for {interface_name}"
        )
        log.save()
        counter_increment(COUNTER_ERRORS)
        error = Error()
        error.description = (
            "Could not get interface data. Please contact your administrator!"
        )
        return error_page(request=request, group=group, switch=switch, error=error)

    log.type = LOG_TYPE_CHANGE
    if new_state == POE_PORT_ADMIN_ENABLED:
        log.action = LOG_CHANGE_INTERFACE_POE_UP
        log.description = f"Interface {interface.name}: Enabling PoE"
        state = "Enabled"
    else:
        log.action = LOG_CHANGE_INTERFACE_POE_DOWN
        log.description = f"Interface {interface.name}: Disabling PoE"
        state = "Disabled"

    if not interface.poe_entry:
        # should not happen...
        log.type = LOG_TYPE_ERROR
        log.description = f"Interface {interface.name} does not support PoE"
        error = Error()
        error.status = True
        error.description = log.descr
        log.save()
        counter_increment(COUNTER_ERRORS)
        return error_page(request=request, group=group, switch=switch, error=error)

    # do the work:
    retval = conn.set_interface_poe_status(interface, new_state)
    if retval < 0:
        log.description = f"ERROR: {conn.error.description}"
        log.type = LOG_TYPE_ERROR
        log.save()
        counter_increment(COUNTER_ERRORS)
        return error_page(request=request, group=group, switch=switch, error=conn.error)

    # indicate we need to save config!
    conn.set_save_needed(True)

    # and save cachable/session data
    conn.save_cache()

    log.save()
    counter_increment(COUNTER_CHANGES)

    description = f"Interface {interface.name} PoE is now {state}"
    return success_page(request, group, switch, description)


#
# Toggle PoE status Down then Up
#
@login_required(redirect_field_name=None)
def interface_poe_down_up(request, group_id, switch_id, interface_name):
    """
    Toggle the PoE status of an interfaces. I.e disable, wait some, then enable again.
    """
    group = get_object_or_404(SwitchGroup, pk=group_id)
    switch = get_object_or_404(Switch, pk=switch_id)

    if not rights_to_group_and_switch(request, group_id, switch_id):
        error = Error()
        error.status = True
        error.description = "Access denied!"
        counter_increment(COUNTER_ACCESS_DENIED)
        return error_page(request=request, group=False, switch=False, error=error)

    log = Log(
        user=request.user,
        ip_address=get_remote_ip(request),
        switch=switch,
        group=group,
        if_name=interface_name,
    )

    try:
        conn = get_connection_object(request, group, switch)
    except Exception:
        log.type = LOG_TYPE_ERROR
        log.action = LOG_CONNECTION_ERROR
        log.description = "Could not get connection"
        log.save()
        counter_increment(COUNTER_ERRORS)
        error = Error()
        error.description = "Could not get connection. Please contact your administrator to make sure switch data is correct in the database!"
        return error_page(request=request, group=group, switch=switch, error=error)

    interface = conn.get_interface_by_key(interface_name)
    if not interface:
        log.type = LOG_TYPE_ERROR
        log.description = (
            f"PoE-Down-Up: Error getting interface data for {interface_name}"
        )
        log.save()
        counter_increment(COUNTER_ERRORS)
        error = Error()
        error.description = (
            "Could not get interface data. Please contact your administrator!"
        )
        return error_page(request=request, group=group, switch=switch, error=error)

    log.type = LOG_TYPE_CHANGE
    log.action = LOG_CHANGE_INTERFACE_POE_TOGGLE_DOWN_UP
    log.description = f"Interface {interface.name}: PoE Toggle Down-Up"

    if not interface.poe_entry:
        # should not happen...
        log.type = LOG_TYPE_ERROR
        log.description = f"Interface {interface.name} does not support PoE"
        error = Error()
        error.status = True
        error.description = log.description
        log.save()
        counter_increment(COUNTER_ERRORS)
        return error_page(request=request, group=group, switch=switch, error=error)

    # the PoE information (index) is kept in the interface.poe_entry
    if not interface.poe_entry.admin_status == POE_PORT_ADMIN_ENABLED:
        # should not happen...
        log.type = LOG_TYPE_ERROR
        log.description = f"Interface {interface.name} does not have PoE enabled"
        error = Error()
        error.status = True
        error.description = log.description
        log.save()
        counter_increment(COUNTER_ERRORS)
        return error_page(request=request, group=group, switch=switch, error=error)

    # disable PoE:
    if not conn.set_interface_poe_status(interface, POE_PORT_ADMIN_DISABLED):
        log.description = (
            f"ERROR: Toggle-Disable PoE on {interface.name} - {conn.error.description}"
        )
        log.type = LOG_TYPE_ERROR
        log.save()
        counter_increment(COUNTER_ERRORS)
        return error_page(request=request, group=group, switch=switch, error=conn.error)

    # delay to let the device cold-boot properly
    time.sleep(settings.POE_TOGGLE_DELAY)

    # and enable PoE again...
    if not conn.set_interface_poe_status(interface, POE_PORT_ADMIN_ENABLED):
        log.description = (
            f"ERROR: Toggle-Enable PoE on {interface.name} - {conn.error.description}"
        )
        log.type = LOG_TYPE_ERROR
        log.save()
        counter_increment(COUNTER_ERRORS)
        return error_page(request=request, group=group, switch=switch, error=conn.error)

    # no state change, so no save needed!
    log.save()

    # and save cachable/session data
    conn.save_cache()
    counter_increment(COUNTER_CHANGES)

    description = f"Interface {interface.name} PoE was toggled!"
    return success_page(request, group, switch, description)


@login_required(redirect_field_name=None)
def switch_save_config(request, group_id, switch_id, view):
    """
    This will save the running config to flash/startup/whatever, on supported platforms
    """
    group = get_object_or_404(SwitchGroup, pk=group_id)
    switch = get_object_or_404(Switch, pk=switch_id)

    if not rights_to_group_and_switch(request, group_id, switch_id):
        error = Error()
        error.description = "Access denied!"
        counter_increment(COUNTER_ACCESS_DENIED)
        return error_page(request=request, group=False, switch=False, error=error)

    log = Log(
        user=request.user,
        ip_address=get_remote_ip(request),
        switch=switch,
        group=group,
        action=LOG_SAVE_SWITCH,
        type=LOG_TYPE_CHANGE,
        description="Saving switch config",
    )

    try:
        conn = get_connection_object(request, group, switch)
    except Exception:
        log.type = LOG_TYPE_ERROR
        log.action = LOG_CONNECTION_ERROR
        log.description = "Could not get connection"
        log.save()
        counter_increment(COUNTER_ERRORS)
        error = Error()
        error.description = "Could not get connection. Please contact your administrator to make sure switch data is correct in the database!"
        return error_page(request=request, group=group, switch=switch, error=error)

    if conn.save_needed and conn.can_save_config:
        # we can save
        if conn.save_running_config() < 0:
            # an error happened!
            log.type = LOG_TYPE_ERROR
            log.save()
            counter_increment(COUNTER_ERRORS)
            return error_page(
                request=request, group=group, switch=switch, error=conn.error
            )

        # clear save flag
        conn.set_save_needed(False)

        # save cachable/session data
        conn.save_cache()

    else:
        log.type = LOG_TYPE_ERROR
        log.description = "Can not save config"
        log.save()
        counter_increment(COUNTER_ERRORS)
        error = Error()
        error.description = (
            "This switch model cannot save or does not need to save the config"
        )
        conn.set_save_needed(
            False
        )  # clear flag that should not be set in the first place!
        return error_page(request=request, group=group, switch=switch, error=error)

    # all OK
    log.save()

    description = f"Config was saved for {switch.name}"
    return success_page(request, group, switch, description)


@login_required(redirect_field_name=None)
def switch_cmd_output(request, group_id, switch_id):
    """
    Go parse a global switch command that was submitted in the form
    """
    command_id = int(request.POST.get("command_id", -1))
    return switch_view(
        request=request,
        group_id=group_id,
        switch_id=switch_id,
        view="basic",
        command_id=command_id,
    )


@login_required(redirect_field_name=None)
def switch_cmd_template_output(request, group_id, switch_id):
    """
    Go parse a switch command template that was submitted in the form
    """
    group = get_object_or_404(SwitchGroup, pk=group_id)
    switch = get_object_or_404(Switch, pk=switch_id)

    if not rights_to_group_and_switch(request, group_id, switch_id):
        error = Error()
        error.description = "Access denied!"
        counter_increment(COUNTER_ACCESS_DENIED)
        return error_page(request=request, group=False, switch=False, error=error)

    template_id = int(request.POST.get("template_id", -1))
    t = get_object_or_404(CommandTemplate, pk=template_id)

    # now build the command template:
    values = {}
    errors = False
    error_string = ""

    """
    do field / list validation here. This can likely be simplified - needs work!
    """
    # do we need to parse field1:
    if "{{field1}}" in t.template:
        field1 = request.POST.get("field1", False)
        if field1:
            if string_matches_regex(field1, t.field1_regex):
                values["field1"] = str(field1)
            else:
                errors = True
                error_string = f"{ t.field1_name } - Invalid entry: { field1 }"
        else:
            # not found in form (or empty), but reqired!
            errors = True
            error_string = f"{ t.field1_name } - cannot be blank!"

    # do we need to parse field2:
    if "{{field2}}" in t.template:
        field2 = request.POST.get("field2", False)
        if field2:
            if string_matches_regex(field2, t.field2_regex):
                values["field2"] = str(field2)
            else:
                errors = True
                error_string += f"<br/>{ t.field2_name } - Invalid entry: { field2 }"
        else:
            # not found in form (or empty), but reqired!
            errors = True
            error_string += f"<br/>{ t.field2_name } - cannot be blank!"

    # do we need to parse field3:
    if "{{field3}}" in t.template:
        field3 = request.POST.get("field3", False)
        if field3:
            if string_matches_regex(field3, t.field3_regex):
                values["field3"] = str(field3)
            else:
                errors = True
                error_string += f"<br/>{ t.field3_name } - Invalid entry: { field3 }"
        else:
            # not found in form (or empty), but reqired!
            errors = True
            error_string += f"<br/>{ t.field3_name } - cannot be blank!"

    # do we need to parse field4:
    if "{{field4}}" in t.template:
        field4 = request.POST.get("field4", False)
        if field4:
            if string_matches_regex(field4, t.field4_regex):
                values["field4"] = str(field4)
            else:
                errors = True
                error_string += f"<br/>{ t.field4_name } - Invalid entry: { field4 } "
        else:
            # not found in form (or empty), but reqired!
            errors = True
            error_string += f"<br/>{ t.field4_name } - cannot be blank!"

    # do we need to parse field5:
    if "{{field5}}" in t.template:
        field5 = request.POST.get("field5_regex", False)
        if field5:
            if string_matches_regex(field5, t.field5_regex):
                values["field5"] = str(field5)
            else:
                errors = True
                error_string += f"<br/>{t.field5_name} - Invalid entry: { field5 }"
        else:
            # not found in form (or empty), but reqired!
            errors = True
            error_string += f"<br/>{ t.field5_name } - cannot be blank!"

    # do we need to parse field6:
    if "{{field6}}" in t.template:
        field6 = request.POST.get("field6", False)
        if field6:
            if string_matches_regex(field1, t.field6_regex):
                values["field6"] = str(field6)
            else:
                errors = True
                error_string += f"<br/>{t.field6_name} - Invalid entry: { field6 } "
        else:
            # not found in form (or empty), but reqired!
            errors = True
            error_string += f"<br/>{ t.field6_name } - cannot be blank!"

    # do we need to parse field7:
    if "{{field7}}" in t.template:
        field7 = request.POST.get("field7", False)
        if field7:
            if string_matches_regex(field7, t.field7_regex):
                values["field7"] = str(field7)
            else:
                errors = True
                error_string += f"<br/>{t.field7_name} - Invalid entry: { field7 }"
        else:
            # not found in form (or empty), but reqired!
            errors = True
            error_string += f"<br/>{ t.field7_name } - cannot be blank!"

    # do we need to parse field8:
    if "{{field8}}" in t.template:
        field8 = request.POST.get("field8", False)
        if field8:
            if string_matches_regex(field8, t.field8_regex):
                values["field8"] = str(field8)
            else:
                errors = True
                error_string += f"<br/>{t.field8_name} - Invalid entry: { field8 }"
        else:
            # not found in form (or empty), but reqired!
            errors = True
            error_string += f"<br/>{ t.field8_name } - cannot be blank!"

    # and the pick lists:
    # do we need to parse list1:
    if "{{list1}}" in t.template:
        list1 = request.POST.get("list1", False)
        if list1:
            values["list1"] = str(list1)
        else:
            # not found in form (or empty), but reqired (unlikely to happen for list)!
            errors = True
            error_string += f"<br/>{ t.list1_name } - cannot be blank!"

    # do we need to parse list2:
    if "{{list2}}" in t.template:
        list2 = request.POST.get("list2", False)
        if list2:
            values["list2"] = str(list2)
        else:
            # not found in form (or empty), but reqired (unlikely to happen for list)!
            errors = True
            error_string += f"<br/>{ t.list2_name } - cannot be blank!"

    # do we need to parse list3:
    if "{{list3}}" in t.template:
        list3 = request.POST.get("list3", False)
        if list3:
            values["list3"] = str(list3)
        else:
            # not found in form (or empty), but reqired (unlikely to happen for list)!
            errors = True
            error_string += f"<br/>{ t.list3_name } - cannot be blank!"

    # do we need to parse list4:
    if "{{list4}}" in t.template:
        list4 = request.POST.get("list4", False)
        if list4:
            values["list4"] = str(list4)
        else:
            # not found in form (or empty), but reqired (unlikely to happen for list)!
            errors = True
            error_string += f"<br/>{ t.list4_name } - cannot be blank!"

    # do we need to parse list5:
    if "{{list5}}" in t.template:
        list5 = request.POST.get("list5", False)
        if list5:
            values["list5"] = str(list5)
        else:
            # not found in form (or empty), but reqired (unlikely to happen for list)!
            errors = True
            error_string += f"<br/>{ t.list5_name } - cannot be blank!"

    if errors:
        error = Error()
        error.description = mark_safe(error_string)
        return error_page(request=request, group=group, switch=switch, error=error)

    # now do the template expansion, i.e. Jinja2 rendering:
    template = Template(t.template)
    context = Context(values)
    command = template.render(context)

    return switch_view(
        request=request,
        group_id=group_id,
        switch_id=switch_id,
        view="basic",
        command_id=-1,
        interface_name="",
        command_string=command,
        command_template=t,
    )


@login_required(redirect_field_name=None)
def interface_cmd_output(request, group_id, switch_id, interface_name):
    """
    Parse the interface-specific form and build the commands
    """
    command_id = int(request.POST.get("command_id", -1))
    return switch_view(
        request=request,
        group_id=group_id,
        switch_id=switch_id,
        view="basic",
        command_id=command_id,
        interface_name=interface_name,
    )


@login_required(redirect_field_name=None)
def switch_reload(request, group_id, switch_id, view):
    """
    This forces a new reading of basic switch SNMP data
    """

    group = get_object_or_404(SwitchGroup, pk=group_id)
    switch = get_object_or_404(Switch, pk=switch_id)

    if not rights_to_group_and_switch(request, group_id, switch_id):
        error = Error()
        error.description = "Access denied!"
        counter_increment(COUNTER_ACCESS_DENIED)
        return error_page(request=request, group=False, switch=False, error=error)

    log = Log(
        user=request.user,
        ip_address=get_remote_ip(request),
        switch=switch,
        group=group,
        description=f"Reloading device ({view})",
        action=LOG_RELOAD_SWITCH,
        type=LOG_TYPE_VIEW,
    )
    log.save()

    clear_switch_cache(request)
    counter_increment(COUNTER_VIEWS)

    return switch_view(
        request=request, group_id=group_id, switch_id=switch_id, view=view
    )


@login_required(redirect_field_name=None)
def switch_activity(request, group_id, switch_id):
    """
    This shows recent activity for a specific switch
    """
    template_name = "switch_activity.html"

    group = get_object_or_404(SwitchGroup, pk=group_id)
    switch = get_object_or_404(Switch, pk=switch_id)

    if not rights_to_group_and_switch(request, group_id, switch_id):
        error = Error()
        error.description = "Access denied!"
        counter_increment(COUNTER_ACCESS_DENIED)
        return error_page(request=request, group=False, switch=False, error=error)

    # only show this switch. May add more filters later...
    filter = {"switch_id": switch_id}
    logs = Log.objects.all().filter(**filter).order_by("-timestamp")

    # setup pagination of the resulting activity logs
    page_number = int(request.GET.get("page", default=1))
    paginator = Paginator(
        logs, settings.PAGINATE_COUNT
    )  # Show set number of contacts per page.
    logs_page = paginator.get_page(page_number)

    # log my activity
    log = Log(
        user=request.user,
        ip_address=get_remote_ip(request),
        switch=switch,
        group=group,
        type=LOG_TYPE_VIEW,
        action=LOG_VIEW_ALL_LOGS,
        description=f"Viewing Switch Activity Logs (page {page_number})",
    )
    log.save()

    # get the url to this switch:
    switch_url = reverse(
        "switches:switch_basics", kwargs={"group_id": group.id, "switch_id": switch.id}
    )
    # formulate the title and link
    title = mark_safe(
        f'All Activity for <a href="{switch_url}" data-toggle="tooltip" title="Go back to switch">{switch.name}</a>'
    )
    # render the template
    return render(
        request,
        template_name,
        {
            "logs": logs_page,
            "paginator": paginator,
            "group": group,
            "switch": switch,
            "log_title": title,
            "logs_link": False,
        },
    )


@login_required(redirect_field_name=None)
def show_stats(request):
    """
    This shows various site statistics
    """

    template_name = "admin_stats.html"

    # log my activity
    log = Log(
        user=request.user,
        ip_address=get_remote_ip(request),
        type=LOG_TYPE_VIEW,
        action=LOG_VIEW_ADMIN_STATS,
        description="Viewing Site Statistics",
    )
    log.save()

    environment = {
        "Python": f"{sys.version_info[0]}.{sys.version_info[1]}.{sys.version_info[2]}"
    }  # OS environment information
    uname = os.uname()
    environment["OS"] = f"{uname.sysname} ({uname.release})"
    # environment['Version'] = uname.version
    environment["Distro"] = f"{distro.name()} {distro.version(best=True)}"
    environment["Hostname"] = uname.nodename
    environment["Django"] = django.get_version()
    environment["OpenL2M version"] = f"{settings.VERSION} ({settings.VERSION_DATE})"
    import git

    try:
        repo = git.Repo(search_parent_directories=True)
        sha = repo.head.object.hexsha
        short_sha = repo.git.rev_parse(sha, short=8)
        branch = repo.active_branch
        commit_date = time.strftime(
            "%a, %d %b %Y %H:%M UTC", time.gmtime(repo.head.object.committed_date)
        )
        environment["Git version"] = f"{branch} ({short_sha})"
        environment["Git commit"] = commit_date
    except Exception:
        environment["Git version"] = "Not found!"

    db_items = {"Switches": Switch.objects.count()}  # database object item counts
    # need to calculate switchgroup count, as we count only groups with switches!
    group_count = 0
    for group in SwitchGroup.objects.all():
        if group.switches.count():
            group_count += 1
    db_items["Switch Groups"] = group_count
    db_items["Vlans"] = VLAN.objects.count()
    db_items["Vlan Groups"] = VlanGroup.objects.count()
    db_items["SNMP Profiles"] = SnmpProfile.objects.count()
    db_items["Netmiko Profiles"] = NetmikoProfile.objects.count()
    db_items["Commands"] = Command.objects.count()
    db_items["Command Lists"] = CommandList.objects.count()
    db_items["Log Entries"] = Log.objects.count()

    usage = {}  # usage statistics

    filter = {"type": int(LOG_TYPE_CHANGE), "timestamp__date": datetime.date.today()}
    usage["Changes today"] = Log.objects.filter(**filter).count()

    filter = {
        "type": int(LOG_TYPE_CHANGE),
        "timestamp__gte": timezone.now().date() - datetime.timedelta(days=7),
    }
    usage["Changes last 7 days"] = Log.objects.filter(**filter).count()

    filter = {
        "type": int(LOG_TYPE_CHANGE),
        "timestamp__gte": timezone.now().date() - datetime.timedelta(days=31),
    }
    usage["Changes last 31 days"] = Log.objects.filter(**filter).count()

    # the total change count since install from Counter()'changes') object:
    usage["Total Changes"] = Counter.objects.get(name="changes").value

    filter = {"type": int(LOG_TYPE_COMMAND), "timestamp__date": datetime.date.today()}
    usage["Commands today"] = Log.objects.filter(**filter).count()

    filter = {
        "type": int(LOG_TYPE_COMMAND),
        "timestamp__gte": timezone.now().date() - datetime.timedelta(days=7),
    }
    usage["Commands last 7 days"] = Log.objects.filter(**filter).count()

    filter = {
        "type": int(LOG_TYPE_COMMAND),
        "timestamp__gte": timezone.now().date() - datetime.timedelta(days=31),
    }
    usage["Commands last 31 days"] = Log.objects.filter(**filter).count()

    # total number of commands run:
    usage["Total Commands"] = Counter.objects.get(name="commands").value

    user_list = get_current_users()

    # render the template
    return render(
        request,
        template_name,
        {
            "db_items": db_items,
            "usage": usage,
            "environment": environment,
            "user_list": user_list,
        },
    )


#
# "Administrative" views
#


@login_required(redirect_field_name=None)
def admin_activity(request):
    """
    This shows recent activity
    """

    template_name = "admin_activity.html"

    # what do we have rights to:
    if not request.user.is_superuser and not request.user.is_staff:
        # get them out of here!
        # log my activity
        log = Log(
            user=request.user,
            ip_address=get_remote_ip(request),
            type=LOG_TYPE_ERROR,
            action=LOG_VIEW_ALL_LOGS,
            description="Not Allowed to View All Logs",
        )
        log.save()
        error = Error()
        error.status = True
        error.description = "You do not have access to this page!"
        counter_increment(COUNTER_ACCESS_DENIED)
        return error_page(request=request, group=False, switch=False, error=error)

    # log my activity
    log = Log(
        user=request.user,
        ip_address=get_remote_ip(request),
        type=LOG_TYPE_VIEW,
        action=LOG_VIEW_ALL_LOGS,
    )

    page_number = int(request.GET.get("page", default=1))

    # look at query string, and filter as needed
    filter = {}
    if len(request.GET) > 0:
        if request.GET.get("type", ""):
            filter["type"] = int(request.GET["type"])
        if request.GET.get("action", ""):
            filter["action"] = int(request.GET["action"])
        if request.GET.get("user", ""):
            filter["user_id"] = int(request.GET["user"])
        if request.GET.get("switch", ""):
            filter["switch_id"] = int(request.GET["switch"])
        if request.GET.get("group", ""):
            filter["group_id"] = int(request.GET["group"])

    # now set the filter, if found
    if len(filter) > 0:
        logs = Log.objects.all().filter(**filter).order_by("-timestamp")
        log.description = f"Viewing filtered logs: {filter} (page {page_number})"
        title = "Filtered Activities"
    else:
        logs = Log.objects.all().order_by("-timestamp")
        log.description = f"Viewing all logs (page {page_number})"
        title = "All Activities"
    log.save()

    # setup pagination of the resulting activity logs
    paginator = Paginator(
        logs, settings.PAGINATE_COUNT
    )  # Show set number of contacts per page.
    logs_page = paginator.get_page(page_number)

    # render the template
    return render(
        request,
        template_name,
        {
            "logs": logs_page,
            "paginator": paginator,
            "filter": filter,
            "types": LOG_TYPE_CHOICES,
            "actions": LOG_ACTION_CHOICES,
            "switches": Switch.objects.all().order_by("name"),
            "switchgroups": SwitchGroup.objects.all().order_by("name"),
            "users": User.objects.all().order_by("username"),
            "log_title": title,
            "logs_link": False,
        },
    )


def rights_to_group_and_switch(request, group_id, switch_id):
    """
    Check if the current user has rights to this switch in this group
    Returns True if allowed, False if not!
    """
    if request.user.is_superuser or request.user.is_staff:
        return True
    # for regular users, check permissions:
    permissions = get_from_http_session(request, "permissions")
    if (
        permissions
        and isinstance(permissions, dict)
        and int(group_id) in permissions.keys()
    ):
        switches = permissions[int(group_id)]
        if isinstance(switches, dict) and int(switch_id) in switches.keys():
            return True
    return False


def user_can_access_task(request, task=False):
    """
    Check if the current user has rights to this task.
    This needs more work, for now keep it simle.
    Return True or False
    """
    if request.user.is_superuser or request.user.is_staff:
        return True
    if task:
        if task.user == request.user:
            return True
        # does the user have rights to the group of this task?
        permissions = get_from_http_session(request, "permissions")
        if (
            permissions
            and isinstance(permissions, dict)
            and str(task.group.id) in permissions.keys()
        ):
            #  if member of group there is no need to check switch!
            return True
    # deny others
    return False


# Here we implement all api views as classes
class APIInterfaceDetailView(
    APIView,
):
    """
    Return the ARP Information for an interface if there is any to return
    All Interfaces should be integer
    """

    authentication_classes = [
        SessionAuthentication,
        BasicAuthentication,
        TokenAuthentication,
    ]
    permission_classes = [
        IsAuthenticated,
    ]

    def get(
        self,
        request,
        group_id,
        switch_id,
        interface_name="",
    ):
        group, switch = confirm_access_rights(
            request=request,
            group_id=group_id,
            switch_id=switch_id,
        )
        if interface_name:
            conn = get_connection_switch(request=request, group=group, switch=switch)
            data = {
            "interface": interface_name,
            "macaddress": None,
            "vlan": None,
            "state": None,
            "online": None,
            "speed": None,
            }
            if conn.eth_addr_count > 0:
                for key, iface in conn.interfaces.items():
                    if key == interface_name:
                        data["interface"] = interface_name
                        for macaddress, eth in iface.eth.items():
                            if macaddress != "":
                                data["macaddress"] = macaddress
                        if iface.untagged_vlan > 0:
                            data["vlan"] = iface.untagged_vlan
                        if iface.admin_status:
                            data["state"] = "Enabled"
                        else:
                            data["state"] = "Disabled"
                        if iface.oper_status:
                            data["online"] = True
                        else:
                            data["online"] = False
                        if iface.speed:
                            data["speed"] = iface.speed
                return Response(
                    data=data,
                    status=status.HTTP_200_OK,
                )
            return Response(
                data=data,
                status=status.HTTP_404_NOT_FOUND,
            )


class APIInterfaceSpeedView(
    APIView,
):
    """
    Return only the speed data for the selected interface.
    All Interfaces should be integer based
    """

    authentication_classes = [
        SessionAuthentication,
        BasicAuthentication,
        TokenAuthentication,
    ]
    permission_classes = [
        IsAuthenticated,
    ]
    def get(
        self,
        request,
        group_id,
        switch_id,
        interface_name=None,
    ):
        group, switch = confirm_access_rights(
            request=request,
            group_id=group_id,
            switch_id=switch_id,
        )
        if interface_name:
            conn = get_connection_switch(request=request, group=group, switch=switch)
            data = {
                    "interface": interface_name,
                    "macaddress": None,
                    "vlan": None,
                    "state": None,
                    "online": None,
                    "speed": None,
                    }
            if conn.eth_addr_count > 0:
                for key, iface in conn.interfaces.items():
                    if key == interface_name:
                        data["interface"] = interface_name
                        for macaddress, eth in iface.eth.items():
                            if macaddress != "":
                                data["macaddress"] = macaddress
                        if iface.untagged_vlan > 0:
                            data["vlan"] = iface.untagged_vlan
                        if iface.admin_status:
                            data["state"] = "Enabled"
                        else:
                            data["state"] = "Disabled"
                        if iface.oper_status:
                            data["online"] = True
                        else:
                            data["online"] = False
                        if iface.speed:
                            data["speed"] = iface.speed
                return Response(
                    data=data,
                    status=status.HTTP_200_OK,
                )
            return Response(
                    data=data,
                    status=status.HTTP_404_NOT_FOUND,
                )

def get_connection_switch(request, group, switch): 
    try:
        conn = get_connection_object(request, group, switch)
    except ConnectionError as e:
        error = f"The following ConnectionError: {e} occurred."
        dprint(error)
        return Response(
            data=error,
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        if not conn.get_basic_info():
            error = "ERROR in get_basic_switch_info()"
            dprint(error)
        if not conn.get_client_data():
            error = "ERROR in get_client_data()"
            dprint(error)
    except Exception as e:
        error = f"Exception for get switch info {e}"
        dprint(error)
        return Response(
            data=error,
            status=status.HTTP_400_BAD_REQUEST,
        )
    conn.save_cache()
    return conn


def confirm_access_rights(
    request=None,
    group_id=None,
    switch_id=None,
):
    group = get_object_or_404(
        SwitchGroup,
        pk=group_id,
    )
    switch = get_object_or_404(
        Switch,
        pk=switch_id,
    )
    if not rights_to_group_and_switch(
        request=request,
        group_id=group_id,
        switch_id=switch_id,
    ):
        error = Error()
        error.details = "This resource is not accessible for you."
        return Response(
            data=error,
            status=status.HTTP_401_UNAUTHORIZED,
        )
    return group, switch


"""
This class extends the ObtainAuthToken class
"""
class APIObtainAuthToken(ObtainAuthToken):
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(
            raise_exception=True,
        )
        user = serializer.validated_data["user"]
        token, created = Token.objects.get_or_create(user=user)
        return Response(
            {
                "token": token.key,
                "user_id": user.pk,
                "email": user.email,
            }
        )
