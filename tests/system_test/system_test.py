#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import shutil
import subprocess
import sys
from collections import OrderedDict
from commands import getstatusoutput
from os import chdir, environ
from os.path import join, exists, split, abspath, isdir, isfile
from tempfile import mkdtemp
from threading import Timer
from time import time

"""
Module for System Testing

To add a new test add it in the test dictionary in main.
"""

__author__ = "Daniel Aviv"
__email__ = "daniel_avivnotario@hotmail.com"
__credits__ = ["Francisco Montoto", "Francisco Cifuentes"]
__status__ = "Development"

DEFAULT_DUMP_PATH = "/tmp/"
DUMP = ""
EXEC_PATH = ""
CONFIG_CREATOR_PATH = ""

NODE_RDY = "Both socket binded, node ready to talk with the Master."

NODE_TIMEOUT = 5
MASTER_TIMEOUT = 20

DEBUG = False


def erase_dump():
    """Deletes the dump folder, if exists"""
    if exists(DUMP):
        shutil.rmtree(DUMP)
    return 0


def exec_node(config):
    """
    Executes a node linked with a specific configuration file

    :param config: Path of the configuration file
    :return: Returns the node process, the return code and a return message
    """
    if not isdir(EXEC_PATH):
        return None, 1, "ERROR: Path doesn't exists >> " + EXEC_PATH

    if not isdir(join(EXEC_PATH, "src")):
        return None, 1, "ERROR: Path doesn't exists >> " + EXEC_PATH + "/src"

    node = None
    try:
        node = subprocess.Popen(
            [EXEC_PATH + "/src/node",
             "-c",
             config + ".conf"],
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE)
    except OSError:
        return node, 1, "ERROR: Exec could not be accesed >> " + EXEC_PATH + "/src/node"

    timer = Timer(NODE_TIMEOUT, node.terminate)
    timer.start()

    stderr_lines = iter(node.stderr.readline, "")
    for stderr_line in stderr_lines:
        if DEBUG:
            sys.stdout.write("DEBUG::STDERR --> " + stderr_line)
        if NODE_RDY in stderr_line:
            break

    if timer.is_alive():
        timer.cancel()
        return node, 0, ""
    else:
        return node, 1, "FAILURE: Timeout"


def close_node(node_proc):
    """
    Closes a node process, closing also the nodes stdout and stderr

    :param node_proc: The node process to be closed
    """
    if node_proc is not None:
        node_proc.stdout.close()
        node_proc.stderr.close()
        node_proc.terminate()


def close_nodes(nodes):
    """
    Closes various node processes, closing also the nodes stdout and stederr

    :param nodes: An array of nodes processes to be closed
    """
    for node in nodes:
        close_node(node)


def exec_master(master_args, master_name, cryptoki_conf="cryptoki.conf"):
    """
    Executes a master linked with a specific arguments

    :param master_args: Arguments of the process to be run, including the script itself
    :param master_name: Name of the master, for logging purposes
    :param cryptoki_conf: Value of the TCHSM_CONFIG env. variable
    :return: Returns the master process, the return code and a return message
    """
    if isfile(cryptoki_conf):
        environ["TCHSM_CONFIG"] = abspath(cryptoki_conf)
    else:
        return None, 1, "ERROR: TCHSM_CONFIG env. var. could not be set."

    try:
        master = subprocess.Popen(
            master_args,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE)
    except OSError:
        return None, 1, "ERROR: Exec could not be accesed >> " + master_name

    timer = Timer(MASTER_TIMEOUT, master.terminate)
    if master is not None:
        timer.start()

    stdout_data, stderr_data = master.communicate()

    if timer.is_alive():
        timer.cancel()
        debug_output(stdout_data, stderr_data)

        if master.returncode != 0:
            return master, master.returncode, "FAILURE: Master return code: " + str(master.returncode)
        return master, master.returncode, ""
    else:
        debug_output(stdout_data, stderr_data)
        return master, 1, "FAILURE: Timeout"


def close_master(master):
    """
    Closes a master stderr and stdout

    :param master: The master process
    """
    if master is not None:
        master.stdout.close()
        master.stderr.close()


def create_dummy_file():
    """
    Creates a text file with a fixed string on it

    :return: The file descriptor of the file
    """
    fd = open("to_sign.txt", "w")
    fd.write(":)\n")
    return fd


def debug_output(stdout, stderr):
    """
    It prints the content of two output strings line by line

    :param stdout: An output string
    :param stderr: An output string
    """
    if DEBUG:
        for line in stdout.split("\n"):
            if line != "":
                print "DEBUG::STDOUT --> " + line
        for line in stderr.split("\n"):
            if line != "":
                print "DEBUG::STDERR --> " + line


# NODE ONLY TESTS
def test_one_node():
    status, output = getstatusoutput(
        "python " + CONFIG_CREATOR_PATH + " 127.0.0.1:2121:2122")
    if status != 0:
        return 1, "ERROR: Configuration files could not be created."

    proc, ret, mess = exec_node("node1")
    close_node(proc)
    return ret, mess


def test_two_nodes():
    status, output = getstatusoutput(
        "python " + CONFIG_CREATOR_PATH + " 127.0.0.1:2121:2122 127.0.0.1:2123:2124")
    if status != 0:
        return 1, "ERROR: Configuration files could not be created."

    node1, ret1, mess1 = exec_node("node1")
    if ret1 == 1:
        close_node(node1)
        return 1, mess1

    node2, ret2, mess2 = exec_node("node2")

    close_nodes([node1, node2])
    return ret2, mess2


def test_opening_closing_node():
    status, output = getstatusoutput(
        "python " + CONFIG_CREATOR_PATH + " 127.0.0.1:2121:2122")
    if status != 0:
        return 1, "ERROR: Configuration files could not be created."

    node, ret, mess = exec_node("node1")
    if ret == 1:
        close_node(node)
        return 1, mess

    close_node(node)

    node, ret, mess = exec_node("node1")
    close_node(node)
    return ret, mess


def test_open_close_with_node_open():
    status, output = getstatusoutput(
        "python " + CONFIG_CREATOR_PATH + " 127.0.0.1:2121:2122 127.0.0.1:2123:2124")
    if status != 0:
        return 1, "ERROR: Configuration files could not be created."

    node1, ret1, mess1 = exec_node("node1")
    if ret1 == 1:
        close_node(node1)
        return 1, mess1

    node2, ret2, mess2 = exec_node("node2")

    close_node(node1)

    node3, ret3, mess3 = exec_node("node1")
    if ret3 == 1:
        close_nodes([node3, node2])
        return 1, mess3

    close_nodes([node3, node2])
    return ret2, mess2


def test_stress_open_close():
    status, output = getstatusoutput(
        "python " + CONFIG_CREATOR_PATH + " 127.0.0.1:2121:2122")
    if status != 0:
        return 1, "ERROR: Configuration files could not be created."

    for i in range(0, 100):
        proc, ret, mess = exec_node("node1")
        close_node(proc)

        if ret != 0:
            return ret, mess

    return 0, ""


def test_stress_simultaneous():
    proc_array = []

    for port in range(2121, 2121 + 60, 2):
        status, output = getstatusoutput(
            "python " + CONFIG_CREATOR_PATH + " 127.0.0.1:" + str(port) + ":" + str(port + 1))
        if status != 0:
            return 1, "ERROR: Configuration files could not be created."

        proc, ret, mess = exec_node("node1")
        proc_array.append(proc)

        if ret != 0:
            close_nodes(proc_array)
            return ret, mess

    close_nodes(proc_array)
    return 0, ""


# MASTER TESTS
def test_master_n_nodes(master_args, master_name, nb_of_nodes):
    config_creation_string = "python " + CONFIG_CREATOR_PATH
    port = 2121
    for i in range(0, nb_of_nodes):
        config_creation_string += " 127.0.0.1:" + \
            str(port) + ":" + str(port + 1)
        port += 2
    config_creation_string += " -t " + str(MASTER_TIMEOUT)

    status, output = getstatusoutput(config_creation_string)
    if status != 0:
        return 1, "ERROR: Configuration files could not be created."

    open_nodes = []
    for i in range(0, nb_of_nodes):
        node_proc, node_ret, node_mess = exec_node("node" + str(i + 1))
        if node_ret == 1:
            close_nodes(open_nodes)
            return 1, node_mess

        open_nodes.append(node_proc)

    master, master_ret, master_mess = exec_master(
        *fix_dtc_args(master_args, master_name, nb_of_nodes))

    close_nodes(open_nodes)
    close_master(master)
    return master_ret, master_mess


def test_master_one_node(master_args, master_name):
    return test_master_n_nodes(master_args, master_name, 1)


def test_master_two_nodes(master_args, master_name):
    return test_master_n_nodes(master_args, master_name, 2)


def test_master_twice(master_args, master_name):
    config_data = " 127.0.0.1:2121:2122 127.0.0.1:2123:2124 -t " + \
        str(MASTER_TIMEOUT)
    status, output = getstatusoutput(
        "python " + CONFIG_CREATOR_PATH + config_data)

    if status != 0:
        return 1, "ERROR: Configuration files could not be created."

    node_proc1, node_ret1, node_mess1 = exec_node("node1")
    if node_ret1 == 1:
        close_node(node_proc1)
        return 1, node_mess1

    node_proc2, node_ret2, node_mess2 = exec_node("node2")
    if node_ret2 == 1:
        close_nodes([node_proc1, node_proc2])
        return 1, node_mess2

    master, master_ret, master_mess = exec_master(
        *fix_dtc_args(master_args, master_name, 2))
    close_master(master)

    if master_ret != 0:
        close_nodes([node_proc1, node_proc2])
        return master_ret, master_mess

    master, master_ret, master_mess = exec_master(
        *fix_dtc_args(master_args, master_name, 2))

    close_nodes([node_proc1, node_proc2])
    close_master(master)
    return master_ret, master_mess


def test_three_nodes_one_down(master_args, master_name):
    node_info = " 127.0.0.1:2121:2122 127.0.0.1:2123:2124 127.0.0.1:2125:2126 -t " + \
        str(MASTER_TIMEOUT)
    status, output = getstatusoutput(
        "python " + CONFIG_CREATOR_PATH + node_info)
    if status != 0:
        return 1, "ERROR: Configuration files could not be created."

    node_proc1, node_ret1, node_mess1 = exec_node("node1")
    if node_ret1 == 1:
        close_node(node_proc1)
        return 1, node_mess1

    node_proc2, node_ret2, node_mess2 = exec_node("node2")
    if node_ret2 == 1:
        close_nodes([node_proc1, node_proc2])
        return 1, node_mess2

    node_proc3, node_ret3, node_mess3 = exec_node("node3")
    if node_ret2 == 1:
        close_nodes([node_proc1, node_proc2, node_proc3])
        return 1, node_mess3

    master, master_ret, master_mess = exec_master(
        *fix_dtc_args(master_args, master_name, 3))
    close_master(master)

    if master_ret != 0:
        close_nodes([node_proc1, node_proc2, node_proc3])
        return master_ret, master_mess

    close_node(node_proc3)

    master, master_ret, master_mess = exec_master(
        *fix_dtc_args(master_args, master_name, 3))
    close_nodes([node_proc1, node_proc2])
    close_master(master)
    if master_ret != 0:
        return 0, ""
    else:
        return 1, "FAILURE: The test should fail, as it should not generate keys."


def test_insuff_threshold_bordercase(master_args, master_name):
    config_data = " 127.0.0.1:2121:2122 -ct -th 0 -t " + str(MASTER_TIMEOUT)
    status, output = getstatusoutput(
        "python " + CONFIG_CREATOR_PATH + config_data
    )
    if status != 0:
        return 1, "ERROR: Configuration files could not be created."

    node_proc, node_ret, node_mess = exec_node("node1")
    if node_ret == 1:
        close_node(node_proc)
        return 1, node_mess

    master, master_ret, master_mess = exec_master(
        *fix_dtc_args(master_args, master_name, 1, 0))
    close_node(node_proc)
    close_master(master)

    if master_ret != 0:
        return 0, ""
    else:
        return 1, "FAILURE: The master should not be able to sign."


def test_insuff_threshold(master_args, master_name):
    node_info = " 127.0.0.1:2121:2122 127.0.0.1:2123:2124 127.0.0.1:2125:2126"
    config_info = node_info + " -ct -th 3 -t " + str(MASTER_TIMEOUT)
    status, output = getstatusoutput(
        "python " + CONFIG_CREATOR_PATH + config_info
    )
    if status != 0:
        return 1, "ERROR: Configuration files could not be created."

    node_proc1, node_ret1, node_mess1 = exec_node("node1")
    if node_ret1 == 1:
        close_node(node_proc1)
        return 1, node_mess1

    node_proc2, node_ret2, node_mess2 = exec_node("node2")
    if node_ret2 == 1:
        close_nodes([node_proc1, node_proc2])
        return 1, node_mess2

    node_proc3, node_ret3, node_mess3 = exec_node("node3")
    if node_ret2 == 1:
        close_nodes([node_proc1, node_proc2, node_proc3])
        return 1, node_mess3

    master, master_ret, master_mess = exec_master(
        *fix_dtc_args(master_args, master_name, 3, 3))
    close_master(master)

    if master_ret == 0:
        close_nodes([node_proc1, node_proc2])
        return 1, "FAILURE: The master should not be able to sign."

    close_node(node_proc3)

    master, master_ret, master_mess = exec_master(
        *fix_dtc_args(master_args, master_name, 3, 3))
    close_nodes([node_proc1, node_proc2])
    close_master(master)

    if master_ret != 0:
        return 0, ""
    else:
        return 1, "FAILURE: The master should not be able to sign."


def test_three_nodes_two_open(master_args, master_name):
    node_info = " 127.0.0.1:2121:2122 127.0.0.1:2123:2124 127.0.0.1:2125:2126"
    config_data = node_info + " -t " + str(MASTER_TIMEOUT)
    status, output = getstatusoutput(
        "python " + CONFIG_CREATOR_PATH + config_data
    )
    if status != 0:
        return 1, "ERROR: Configuration files could not be created."

    node_proc1, node_ret1, node_mess1 = exec_node("node1")
    if node_ret1 == 1:
        close_node(node_proc1)
        return 1, node_mess1

    node_proc2, node_ret2, node_mess2 = exec_node("node2")
    if node_ret2 == 1:
        close_nodes([node_proc1, node_proc2])
        return 1, node_mess2

    master, master_ret, master_mess = exec_master(
        *fix_dtc_args(master_args, master_name, 3))
    close_nodes([node_proc1, node_proc2])
    close_master(master)
    if master_ret != 0:
        return 0, ""
    else:
        return 1, "FAILURE: The test should fail, as it should not generate keys."


def test_master_stress_open_close(master_args, master_name):
    config_data = " 127.0.0.1:2121:2122 127.0.0.1:2123:2124 -t " + \
        str(MASTER_TIMEOUT)
    status, output = getstatusoutput(
        "python " + CONFIG_CREATOR_PATH + config_data)

    if status != 0:
        return 1, "ERROR: Configuration files could not be created."

    node_proc1, node_ret1, node_mess1 = exec_node("node1")
    if node_ret1 == 1:
        close_node(node_proc1)
        return 1, node_mess1

    node_proc2, node_ret2, node_mess2 = exec_node("node2")
    if node_ret2 == 1:
        close_nodes([node_proc1, node_proc2])
        return 1, node_mess2

    for i in range(0, 10):
        master, master_ret, master_mess = exec_master(
            *fix_dtc_args(master_args, master_name, 2))
        close_master(master)

        if master_ret != 0:
            close_nodes([node_proc1, node_proc2])
            return master_ret, master_mess

    close_nodes([node_proc1, node_proc2])
    return 0, ""


def test_stress_multiple_masters(master_args, master_name):
    config_data = " 127.0.0.1:2121:2122 127.0.0.1:2123:2124 -m 10 -t " + \
        str(MASTER_TIMEOUT)
    status, output = getstatusoutput(
        "python " + CONFIG_CREATOR_PATH + config_data)

    if status != 0:
        return 1, "ERROR: Configuration files could not be created."

    node_proc1, node_ret1, node_mess1 = exec_node("node1")
    if node_ret1 == 1:
        close_node(node_proc1)
        return 1, node_mess1

    node_proc2, node_ret2, node_mess2 = exec_node("node2")
    if node_ret2 == 1:
        close_nodes([node_proc1, node_proc2])
        return 1, node_mess2

    for i in range(1, 11):
        fixed_args, master_name = fix_dtc_args(
            master_args, master_name, 2, index=i)
        master, master_ret, master_mess = exec_master(
            fixed_args, master_name, "cryptoki" + str(i) + ".conf")
        close_master(master)

        if master_ret != 0:
            close_nodes([node_proc1, node_proc2])
            return master_ret, master_mess

    close_nodes([node_proc1, node_proc2])
    return 0, ""


def test_cryptoki_wout_key():
    config_data = " 127.0.0.1:2121:2122 127.0.0.1:2123:2124 -t " + \
        str(MASTER_TIMEOUT)
    status, output = getstatusoutput(
        "python " + CONFIG_CREATOR_PATH + config_data)

    if status != 0:
        return 1, "ERROR: Configuration files could not be created."

    node_proc1, node_ret1, node_mess1 = exec_node("node1")
    if node_ret1 == 1:
        close_node(node_proc1)
        return 1, node_mess1

    node_proc2, node_ret2, node_mess2 = exec_node("node2")
    if node_ret2 == 1:
        close_nodes([node_proc1, node_proc2])
        return 1, node_mess2

    dummy_file = create_dummy_file()
    master_args = [join(
                   EXEC_PATH,
                   "tests/system_test/pkcs_11_test"),
                   "-cf",
                   dummy_file.name,
                   "-p",
                   "1234"]
    master_name = "pkcs_11_test"
    master, master_ret, master_mess = exec_master(
        *fix_dtc_args(master_args, master_name, 2))
    close_master(master)

    if master_ret != 0:
        close_nodes([node_proc1, node_proc2])
        return master_ret, master_mess

    master_args = [join(
                   EXEC_PATH,
                   "tests/system_test/pkcs_11_test"),
                   "-f",
                   dummy_file.name,
                   "-p",
                   "1234"]
    master_name = "pkcs_11_test"
    master, master_ret, master_mess = exec_master(
        *fix_dtc_args(master_args, master_name, 2))
    dummy_file.close()

    close_nodes([node_proc1, node_proc2])
    close_master(master)
    return master_ret, master_mess


def test_two_masters_one_nodes(master_args, master_name):
    config_data = " 127.0.0.1:2121:2122 -m 2 -t " + str(MASTER_TIMEOUT)
    status, output = getstatusoutput(
        "python " + CONFIG_CREATOR_PATH + config_data)

    if status != 0:
        return 1, "ERROR: Configuration files could not be created."

    node_proc1, node_ret1, node_mess1 = exec_node("node1")
    if node_ret1 == 1:
        close_node(node_proc1)
        return 1, node_mess1

    fixed_args, master_name = fix_dtc_args(master_args, master_name, 1)
    master, master_ret, master_mess = exec_master(
        fixed_args, master_name, "cryptoki1.conf")
    close_master(master)

    if master_ret != 0:
        close_node(node_proc1)
        return master_ret, master_mess

    fixed_args, master_name = fix_dtc_args(master_args, master_name, 1)
    master, master_ret, master_mess = exec_master(
        fixed_args, master_name, "cryptoki2.conf")

    close_node(node_proc1)
    close_master(master)
    return master_ret, master_mess


def test_two_masters_two_nodes(master_args, master_name):
    config_data = " 127.0.0.1:2121:2122 127.0.0.1:2123:2124 -m 2 -t " + \
        str(MASTER_TIMEOUT)
    status, output = getstatusoutput(
        "python " + CONFIG_CREATOR_PATH + config_data)

    if status != 0:
        return 1, "ERROR: Configuration files could not be created."

    node_proc1, node_ret1, node_mess1 = exec_node("node1")
    if node_ret1 == 1:
        close_node(node_proc1)
        return 1, node_mess1

    node_proc2, node_ret2, node_mess2 = exec_node("node2")
    if node_ret2 == 1:
        close_nodes([node_proc1, node_proc2])
        return 1, node_mess2

    fixed_args, master_name = fix_dtc_args(
        master_args, master_name, 2, index=1)
    master, master_ret, master_mess = exec_master(
        fixed_args, master_name, "cryptoki1.conf")
    close_master(master)

    if master_ret != 0:
        close_nodes([node_proc1, node_proc2])
        return master_ret, master_mess

    fixed_args, master_name = fix_dtc_args(
        master_args, master_name, 2, index=2)
    master, master_ret, master_mess = exec_master(
        fixed_args, master_name, "cryptoki2.conf")

    close_nodes([node_proc1, node_proc2])
    close_master(master)
    return master_ret, master_mess


def test_two_masters_simultaneous(master_args, master_name):
    config_data = " 127.0.0.1:2121:2122 127.0.0.1:2123:2124 -m 2 -t " + \
        str(MASTER_TIMEOUT)
    status, output = getstatusoutput(
        "python " + CONFIG_CREATOR_PATH + config_data)

    if status != 0:
        return 1, "ERROR: Configuration files could not be created."

    node_proc1, node_ret1, node_mess1 = exec_node("node1")
    if node_ret1 == 1:
        close_node(node_proc1)
        return 1, node_mess1

    node_proc2, node_ret2, node_mess2 = exec_node("node2")
    if node_ret2 == 1:
        close_nodes([node_proc1, node_proc2])
        return 1, node_mess2

    fixed_args, master_name = fix_dtc_args(
        master_args, master_name, 2, index=1)
    master1, master_ret1, master_mess1 = exec_master(
        fixed_args, master_name, "cryptoki1.conf")

    fixed_args, master_name = fix_dtc_args(
        master_args, master_name, 2, index=2)
    master2, master_ret2, master_mess2 = exec_master(
        fixed_args, master_name, "cryptoki2.conf")

    if master_ret1 != 0:
        close_nodes([node_proc1, node_proc2])
        return master_ret1, master_mess1

    if master_ret2 != 0:
        close_nodes([node_proc1, node_proc2])
        return master_ret2, master_mess2

    close_nodes([node_proc1, node_proc2])
    close_master(master1)
    close_master(master2)
    return 0, ""


def test_two_masters_thres2_nodes3(master_args, master_name):
    info = " 127.0.0.1:2121:2122 127.0.0.1:2123:2124 127.0.0.1:2125:2126 -m 2 -t " + \
        str(MASTER_TIMEOUT)
    status, output = getstatusoutput("python " + CONFIG_CREATOR_PATH + info)
    if status != 0:
        return 1, "ERROR: Configuration files could not be created."

    node_proc1, node_ret1, node_mess1 = exec_node("node1")
    if node_ret1 == 1:
        close_node(node_proc1)
        return 1, node_mess1

    node_proc2, node_ret2, node_mess2 = exec_node("node2")
    if node_ret2 == 1:
        close_nodes([node_proc1, node_proc2])
        return 1, node_mess2

    fixed_args, master_name = fix_dtc_args(
        master_args, master_name, 3, index=1)
    master1, master_ret1, master_mess1 = exec_master(
        fixed_args, master_name, "cryptoki1.conf")
    close_master(master1)

    if master_ret1 == 0:
        close_nodes([node_proc1, node_proc2])
        return 1, "FAILURE: The test should fail, as it should not generate keys."

    fixed_args, master_name = fix_dtc_args(
        master_args, master_name, 3, index=2)
    master2, master_ret2, master_mess2 = exec_master(
        fixed_args, master_name, "cryptoki2.conf")

    close_nodes([node_proc1, node_proc2])
    close_master(master2)
    if master_ret2 != 0:
        return 0, ""
    else:
        return 1, "FAILURE: The test should fail, as it should not generate keys."


# INTERFACES FOR DIFFERENT TESTS
def perform_test_on_pkcs11(test):
    """
    Interface for running the tests on pkcs11_master_test

    :param test: Test to be run
    :return: Test return code and return message
    """
    dummy_file = create_dummy_file()
    master_args = [join(
                   EXEC_PATH,
                   "tests/system_test/pkcs_11_test"),
                   "-cf",
                   dummy_file.name,
                   "-p",
                   "1234"]
    ret, mess = test(master_args, "pkcs_11_test")

    dummy_file.close()
    return ret, mess


def perform_test_on_dtc(test):
    """
    Interface for running the tests on dtc_master_test

    :param test: Test to be run
    :return: Test return code and return message
    """
    config_path = join(DUMP, "master.conf")
    master_args = [join(
                   EXEC_PATH,
                   "tests/system_test/dtc_master_test"),
                   config_path]

    return test(master_args, "dtc_master_test")


def pretty_print(index, name, result, mess, runtime, verbosity):
    """
    Prints legible information of the test output

    :param index: Test index
    :param name: Test name
    :param result: Test return code
    :param mess: Test return message
    :param runtime: Test runtime
    :param verbosity: If this is true, this will print the passing tests too
    """
    if result == 0:
        if verbosity:
            print str(index) + ".- " + name + " passed! Run time: " + str(runtime)[:6] + " seconds."
    else:
        print str(index) + ".- " + name + " failed!"
        print "      " + str(mess)


def fix_dtc_args(
        master_args,
        master_name,
        nb_of_nodes,
        threshold=None,
        index=None):
    """
    Method that is used to fix the master arguments in the case of dtc

    :param master_args: Original arguments
    :param master_name: Master name, this will only do modifications if this is equals to "dtc_master_test"
    :param nb_of_nodes: Total number of nodes
    :param threshold: Connection threshold
    :param index: Index of the master
    :return: It returns an aray with the fixed arguments and the master name
    """
    fixed_master_args = list(master_args)

    if master_name == "dtc_master_test":
        fixed_master_args.append(str(nb_of_nodes))
        if threshold is not None:
            fixed_master_args.append(str(threshold))

        if index is not None:
            conf_path = master_args[1]
            fixed_master_args[1] = join(
                split(conf_path)[0],
                "master" + str(index) + ".conf")

    return fixed_master_args, master_name


def main(argv=None):
    global NODE_TIMEOUT
    global MASTER_TIMEOUT

    parser = argparse.ArgumentParser(description="System Testing")
    parser.add_argument("build_path",
                        help="path of the folder where the project is build",
                        type=str)
    parser.add_argument("-d",
                        "--dump_path",
                        help="specify whether you would like to change to path of the dump files",
                        default=DEFAULT_DUMP_PATH,
                        type=str)
    parser.add_argument("--debug",
                        help="does not pipe master and node stderr",
                        default=False,
                        action="store_true")
    parser.add_argument("-f",
                        "--fail_fast",
                        help="specify this if you want to stop the test case as soon as it fails one test",
                        default=False,
                        action="store_true")
    parser.add_argument("-m",
                        "--master_timeout",
                        help="maximum time for masters to respond (default: " + str(
                            MASTER_TIMEOUT) + " seg)",
                        default=MASTER_TIMEOUT,
                        type=int)
    parser.add_argument("-n",
                        "--node_timeout",
                        help="maximum time for nodes to respond (default: " + str(
                            NODE_TIMEOUT) + " seg)",
                        default=NODE_TIMEOUT,
                        type=int)
    parser.add_argument("-r",
                        "--run_only",
                        help="only runs the tests that contain this text",
                        default="",
                        type=str)
    parser.add_argument("-s",
                        "--store_failed_dumps",
                        help="specify this if you want to save dump folders",
                        default=False,
                        action="store_true")
    parser.add_argument("-v",
                        "--verbosity",
                        help="specify this if you want to see every running test",
                        default=False,
                        action="store_true")
    parser.add_argument("-w",
                        "--with_stress_tests",
                        help="specify this if you want to add stress tests to the test case",
                        default=False,
                        action="store_true")
    args = parser.parse_args()

    global CONFIG_CREATOR_PATH
    script_path = split(abspath(__file__))[0]
    CONFIG_CREATOR_PATH = join(
        script_path,
        "..",
        "..",
        "scripts",
        "create_config.py")

    NODE_TIMEOUT = args.node_timeout
    MASTER_TIMEOUT = args.master_timeout

    global EXEC_PATH
    EXEC_PATH = abspath(args.build_path)

    global DEBUG
    DEBUG = args.debug

    print(" --- Testing starting --- \n")

    tests = OrderedDict()

    tests["ONE NODE"] = (test_one_node, None)
    tests["TWO NODE"] = (test_two_nodes, None)
    tests["OPEN CLOSED NODE"] = (test_opening_closing_node, None)
    tests["OPEN CLOSE w/ NODE OPEN"] = (
        test_open_close_with_node_open, None)

    tests["DTC ONE NODE"] = (perform_test_on_dtc, test_master_one_node)
    tests["DTC TWO NODES"] = (perform_test_on_dtc, test_master_two_nodes)
    tests["DTC RUN TWICE"] = (perform_test_on_dtc, test_master_twice)
    tests["DTC THREE NODES, ONE FALLS"] = (
        perform_test_on_dtc,
        test_three_nodes_one_down)
    tests["DTC THREE NODES, TWO OPEN"] = (
        perform_test_on_dtc,
        test_three_nodes_two_open)
    tests["DTC INSUFFICIENT THRESHOLD BORDER CASE"] = (
        perform_test_on_dtc,
        test_insuff_threshold_bordercase)
    tests["DTC INSUFFICIENT THRESHOLD"] = (
        perform_test_on_dtc, test_insuff_threshold)
    tests["DTC TWO MASTERS ONE NODE"] = (
        perform_test_on_dtc,
        test_two_masters_one_nodes)
    tests["DTC TWO MASTERS TWO NODE"] = (
        perform_test_on_dtc,
        test_two_masters_two_nodes)
    tests["DTC MASTERS SIMULTANEOUS"] = (
        perform_test_on_dtc,
        test_two_masters_simultaneous)
    tests["DTC MASTERS:2 THRES:2 NODES:3"] = (
        perform_test_on_dtc,
        test_two_masters_thres2_nodes3)

    tests["PKCS11 ONE NODE"] = (
        perform_test_on_pkcs11,
        test_master_one_node)
    tests["PKCS11 TWO NODES"] = (
        perform_test_on_pkcs11,
        test_master_two_nodes)
    tests["PKCS11 RUN TWICE"] = (
        perform_test_on_pkcs11,
        test_master_twice)
    tests["PKCS11 THREE NODES, ONE FALLS"] = (
        perform_test_on_pkcs11,
        test_three_nodes_one_down)
    tests["PKCS11 THREE NODES, TWO OPEN"] = (
        perform_test_on_pkcs11,
        test_three_nodes_two_open)
    tests["PKCS11 INSUFFICIENT THRESHOLD BORDER CASE"] = (
        perform_test_on_pkcs11,
        test_insuff_threshold_bordercase)
    tests["PKCS11 INSUFFICIENT THRESHOLD"] = (
        perform_test_on_pkcs11, test_insuff_threshold)
    tests["PKCS11 TWO MASTERS ONE NODE"] = (
        perform_test_on_pkcs11,
        test_two_masters_one_nodes)
    tests["PKCS11 TWO MASTERS TWO NODE"] = (
        perform_test_on_pkcs11,
        test_two_masters_two_nodes)
    tests["PKCS11 MASTERS SIMULTANEOUS"] = (
        perform_test_on_pkcs11,
        test_two_masters_simultaneous)
    tests["PKCS11 MASTERS:2 THRES:2 NODES:3"] = (
        perform_test_on_pkcs11,
        test_two_masters_thres2_nodes3)
    tests["PKCS11 SAME DATABASE"] = (test_cryptoki_wout_key, None)

    stress_tests = OrderedDict()
    stress_tests["NODE STRESS OPEN CLOSE"] = (test_stress_open_close, None)
    stress_tests["NODE STRESS SIMULTANEOUS"] = (test_stress_simultaneous, None)

    stress_tests["DTC STRESS SAME NODE"] = (
        perform_test_on_dtc,
        test_master_stress_open_close)
    stress_tests["DTC STRESS MULTIPLE MASTERS"] = (
        perform_test_on_dtc,
        test_stress_multiple_masters)

    stress_tests["PKCS11 STRESS SAME NODE"] = (
        perform_test_on_pkcs11,
        test_master_stress_open_close)
    stress_tests["PKCS11 STRESS MULTIPLE MASTERS"] = (
        perform_test_on_pkcs11,
        test_stress_multiple_masters)

    if args.with_stress_tests:
        for k, v in stress_tests.iteritems():
            tests[k] = v

    tests_passed = 0
    tests_run = 0
    total_time = 0

    dump_path = abspath(args.dump_path)
    if not exists(dump_path):
        print "ERROR: Dump path doesn't exists >> " + dump_path

    for index, test_info in enumerate(tests.iteritems()):
        name, test = test_info
        func, func_args = test

        if args.run_only in name:
            global DUMP
            dump_prefix = "libdtc_test_" + str(index + 1) + "_"
            DUMP = mkdtemp(prefix=dump_prefix, dir=dump_path)
            chdir(DUMP)

            start = time()
            if DEBUG:
                print "\nRunning: " + name + " -->"

            if func_args is None:
                result, mess = func()
            else:
                result, mess = func(func_args)

            end = time()
            total_time += end - start

            chdir("..")
            if result == 0:
                tests_passed += 1
                erase_dump()

            if not args.store_failed_dumps:
                erase_dump()

            pretty_print(
                index + 1,
                name,
                result,
                mess,
                end - start,
                args.verbosity)
            tests_run += 1

            if args.fail_fast and result != 0:
                break

    if tests_run == 0:
        print(" --- No tests run ---")
    else:
        test_percentage = str(
            100 * float(tests_passed) / float(tests_run))[:5] + "%"
        passing_string = "|" * tests_passed + \
            " " * (tests_run - tests_passed)
        print("\n --- Tests passed " + str(tests_passed) + "/" + str(tests_run) +
              " (" + test_percentage + "): [" + passing_string + "] ---")
        print(" --- Total run time: " + str(total_time)[:6] + " seconds ---")

    return tests_run - tests_passed


if __name__ == "__main__":
    sys.exit(main(sys.argv))
