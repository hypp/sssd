"""
SSSD LDAP provider tests

:requirement: IDM-SSSD-REQ : LDAP Provider
"""

from __future__ import annotations

import pytest
from sssd_test_framework.roles.client import Client
from sssd_test_framework.roles.ldap import LDAP
from sssd_test_framework.topology import KnownTopology


@pytest.mark.ticket(bz=[795044, 1695574])
@pytest.mark.importance("critical")
@pytest.mark.authentication
@pytest.mark.parametrize("modify_mode", ["exop", "ldap_modify"])
@pytest.mark.topology(KnownTopology.LDAP)
def test_ldap__change_password(client: Client, ldap: LDAP, modify_mode: str):
    """
    :title: Change password with "ldap_pwmodify_mode" set to @modify_mode
    :setup:
        1. Add user to LDAP, set his password
        2. Allow user to change his password
        3. Set "ldap_pwmodify_mode"
        4. Start SSSD
    :steps:
        1. Authenticate user with old password
        2. Change password of user to new password
        3. Authenticate user with new password
        4. Authenticate user with old password
    :expectedresults:
        1. User is authenticated
        2. Password is changed successfully
        3. User is authenticated
        4. User is not authenticated
    :customerscenario: True
    """
    user = "user1"
    old_pass = "Secret123"
    new_pass = "New_password123"

    ldap.user(user).add(password=old_pass)
    ldap.aci.add('(targetattr="userpassword")(version 3.0; acl "pwp test"; allow (all) userdn="ldap:///self";)')

    client.sssd.domain["ldap_pwmodify_mode"] = modify_mode
    client.sssd.start()

    assert client.auth.ssh.password(user, old_pass), "Authentication with old correct password failed"

    assert client.auth.passwd.password(user, old_pass, new_pass), "Password change was not successful"

    assert client.auth.ssh.password(user, new_pass), "Authentication with new correct password failed"
    assert not client.auth.ssh.password(user, old_pass), "Authentication with old incorrect password did not fail"


@pytest.mark.ticket(bz=[795044, 1695574])
@pytest.mark.parametrize("modify_mode", ["exop", "ldap_modify"])
@pytest.mark.topology(KnownTopology.LDAP)
def test_ldap__change_password_new_pass_not_match(client: Client, ldap: LDAP, modify_mode: str):
    """
    :title: Change password with "ldap_pwmodify_mode" set to @modify_mode, but retyped password do not match
    :setup:
        1. Add user to LDAP, set his password
        2. Allow user to change his password
        3. Set "ldap_pwmodify_mode"
        4. Start SSSD
    :steps:
        1. Change password to new password, but retyped password is different
    :expectedresults:
        1. Password change is not successful
    :customerscenario: True
    """
    ldap.user("user1").add(password="Secret123")
    ldap.aci.add('(targetattr="userpassword")(version 3.0; acl "pwp test"; allow (all) userdn="ldap:///self";)')

    client.sssd.domain["ldap_pwmodify_mode"] = modify_mode
    client.sssd.start()

    assert not client.auth.passwd.password(
        "user1", "Secret123", "Red123", "Hat000"
    ), "Password changed successfully, which is not expected"


@pytest.mark.ticket(bz=[795044, 1695574, 1795220])
@pytest.mark.parametrize("modify_mode", ["exop", "ldap_modify"])
@pytest.mark.topology(KnownTopology.LDAP)
def test_ldap__change_password_lowercase(client: Client, ldap: LDAP, modify_mode: str):
    """
    :title: Change password to lower-case letters, password check fail
    :setup:
        1. Add user to LDAP, set his password
        2. Allow user to change his password
        3. Set "passwordCheckSyntax" to "on"
        4. Set "ldap_pwmodify_mode"
        5. Start SSSD
    :steps:
        1. Change password to new password, but all letters are lower-case
        2. Check logs
    :expectedresults:
        1. Password change failed
        2. Password change failure is logged
    :customerscenario: True
    """
    ldap.user("user1").add(password="Secret123")
    ldap.aci.add('(targetattr="userpassword")(version 3.0; acl "pwp test"; allow (all) userdn="ldap:///self";)')
    ldap.ldap.modify("cn=config", replace={"passwordCheckSyntax": "on"})

    client.sssd.domain["ldap_pwmodify_mode"] = modify_mode
    client.sssd.start()

    assert not client.auth.passwd.password(
        "user1", "Secret123", "red_32"
    ), "Password changed successfully, which is not expected"

    assert (
        "pam_sss(passwd:chauthtok): User info message: Password change failed."
        in client.host.ssh.run("journalctl").stdout
    )


@pytest.mark.ticket(bz=[1695574, 1795220])
@pytest.mark.parametrize("modify_mode", ["exop", "ldap_modify"])
@pytest.mark.topology(KnownTopology.LDAP)
def test_ldap__change_password_wrong_current(client: Client, ldap: LDAP, modify_mode: str):
    """
    :title: Password change failed because an incorrect password was used
    :setup:
        1. Add user to LDAP, set his password
        2. Allow user to change his password
        3. Set "ldap_pwmodify_mode"
        4. Start SSSD
    :steps:
        1. Change password to new password, but enter wrong password
    :expectedresults:
        1. Password change is not successful
    :customerscenario: True
    """
    ldap.user("user1").add(password="Secret123")
    ldap.aci.add('(targetattr="userpassword")(version 3.0; acl "pwp test"; allow (all) userdn="ldap:///self";)')

    client.sssd.domain["ldap_pwmodify_mode"] = modify_mode
    client.sssd.start()

    assert not client.auth.passwd.password("user1", "wrong123", "Newpass123"), "Password change did not fail"


@pytest.mark.ticket(bz=[1067476, 1065534])
@pytest.mark.topology(KnownTopology.LDAP)
def test_ldap__user_with_whitespace(client: Client, ldap: LDAP):
    """
    :title: user with a whitespace at beginning is able to login and "id"
    :setup:
        1. Add users " space1" and "user1" to LDAP
        2. Set uids and passwords to users
        3. Clear memcache, logs and db
        4. Start SSSD
    :steps:
        1. Fetch user " space1" information using 'id'
        2. Login user " space1" via ssh
        3. Login user "space1" via ssh
        4. Fetch "user1" user information using 'id'
        5. Fetch " user1" user information using 'id'
    :expectedresults:
        1. " space1" is fetched and has correct id
        2. " space1" is able to login
        3. "space1" is not able to login
        4. "user1" is fetched and has correct id
        5. " user1" is not fetched
    :customerscenario: True
    """
    ldap.user(" space1").add(uid=10011, password="Secret123")
    ldap.user("user1").add(uid=10012, password="Secret123")
    client.sssd.clear(db=True, memcache=True, logs=True)
    client.sssd.start()

    result = client.tools.id(" space1")
    assert result is not None, "User ' space1' was not found"
    assert result.user.id == 10011, "User ' space1' has wrong id"

    assert client.auth.ssh.password(" space1", "Secret123"), "Authentication for user ' space1' failed"
    assert not client.auth.ssh.password("space1", "Secret123"), "Authentication for user 'space1' did not fail"

    result = client.tools.id("user1")
    assert result is not None, "User 'user1' was not found"
    assert result.user.id == 10012, "User 'user1' has wrong id"

    result = client.tools.id(" user1")
    assert result is None, "User ' user1' was found, not expected"
