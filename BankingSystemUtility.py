import bankingsystem_pb2
import json
import logging
import sys
import argparse

_INITIAL_PORT = 50000
_LOGGER = logging.getLogger(__name__)


def log_msg(msg):
    _LOGGER.info(msg)


def initializeLogging():
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('[BRANCH][PID %(process)d] %(message)s')
    handler.setFormatter(formatter)
    _LOGGER.addHandler(handler)
    _LOGGER.setLevel(logging.INFO)


def parseInputFile(inputFile):
    with open(inputFile, "r") as read_file:
        data = json.load(read_file)
        return data


def translateEntityToEnum(entityType):
    if 'branch' == entityType:
        return bankingsystem_pb2.branch
    elif 'customer' == entityType:
        return bankingsystem_pb2.customer
    else:
        raise Exception('Unsupported entity TYPE [%s]' % entityType)


def translateInterfaceToEnum(interfaceType):
    if 'query' == interfaceType:
        return bankingsystem_pb2.query
    elif 'deposit' == interfaceType:
        return bankingsystem_pb2.deposit
    elif 'withdraw' == interfaceType:
        return bankingsystem_pb2.withdraw
    elif 'propagate_deposit' == interfaceType:
        return bankingsystem_pb2.propagate_deposit
    else:
        raise Exception('Unsupported Interface TYPE [%s]' % interfaceType)


def getProcessId(branchID):
    return _INITIAL_PORT + branchID


def parseLocalArgs():
    parser = argparse.ArgumentParser(
        usage='%(prog)s [options]',
        description="CSE531- gRPC Project 1 ")

    parser.add_argument('-i', '--Input', dest="inputFile", required=True, type=str,
                        help='Path to the input file from where Branch/Customer details will be read')
    parser.add_argument('-o', '--Output', dest="outputFile", type=str,
                        help='Path to the output file where the result will be saved')

    clargs = parser.parse_args()
    log_msg('Input file name provided:%s' % clargs.inputFile)
    return clargs.inputFile, clargs.outputFile
