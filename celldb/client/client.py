#!/usr/bin/env python
# celldb
#
import phoenixdb

# All expressions are expressed as a precision decimal. This allows us to
# capture both integral counts and float values.
#
# It is possible to allow for dynamic typing, however, this induces complexity
# for querying and indexing.
DTYPE = "DECIMAL(10, 6)"


def _create_expressions_table(cursor):
    """
    Attempts to create the `Expressions` table, which is indexed by sampleId.
    :param cursor:
    :return cursor:
    """
    cursor.execute("CREATE TABLE Expressions (sampleId VARCHAR PRIMARY KEY)")
    return cursor


def _create_features_table(cursor):
    """
    Attempts to create the `Features` table. To enable dynamic typing add a
    column for the DTYPE.
    :param cursor:
    :return cursor:
    """
    cursor.execute(
        "CREATE TABLE Features "
        "(featureId VARCHAR PRIMARY KEY, featureName VARCHAR)")
    return cursor


def upsert_feature(cursor, featureId, featureName=None):
    """
    Add a feature to the database with an optional featureName.
    :param cursor:
    :param featureId:
    :param featureName:
    :return:
    """
    _alter_expressions_table(cursor, [featureId])
    _upsert_feature(cursor, featureId, featureName)


def _upsert_feature(cursor, featureId, featureName=None):
    """
    Attempts to upsert a row in Features table.
    :param cursor:
    :return:
    """
    if featureName:
        sql = "UPSERT INTO Features(featureId, " \
              "featureName) VALUES ('{}', '{}')".format(
                featureId, featureName)
    else:
        sql = "UPSERT INTO Features(featureId) VALUES ('{}')".format(
                featureId)
    cursor.execute(sql)


def _feature_dtype_list(featureIds):
    """
    Make a formatted string that includes the DTYPE for ease of writing
    queries.
    :param featureIds:
    :return:
    """
    return ", ".join(map(
        lambda x: "{} {}".format(x, DTYPE), featureIds))


def _upsert_sample(cursor, sampleId, featureIds, values):
    """
    Attempt to execute an upsert statement that includes the `values`.

    :param cursor:
    :param sampleId:
    :param featureIds:
    :param values:
    :return:
    """
    sql = "UPSERT INTO Expressions(sampleId, {}) VALUES ('{}', {})".format(
            ", ".join(featureIds),
            sampleId,
            ", ".join(map(lambda x: str(x), values)))
    cursor.execute(sql)

def _alter_expressions_table(cursor, featureIds):
    """
    Takes a list of featureIds and modifies the expressions table to support
    it.
    :param cursor:
    :param featureIds:
    :return:
    """
    feature_list = _feature_dtype_list(featureIds)
    sql = "ALTER TABLE Expressions ADD {}".format(feature_list)
    cursor.execute(sql)

def _upsert_features(cursor, featureIds, featureNames=None):
    """
    Attempts to upsert a featureId row for every featureId.
    :param cursor:
    :param featureIds:
    :return:
    """
    # Consider creating the transposed table here as well in Features
    # to easily find the samples associated with a given key. In this case
    # we simply upsert the key for every feature.
    if featureNames and len(featureIds) == len(featureNames):
        for featureId, featureName in zip(featureIds, featureNames):
            _upsert_feature(cursor, featureId, featureName)
    elif featureNames:
        raise Exception("list of featureIds and featureNames did not match")
    else:
        for featureId in featureIds:
            _upsert_feature(cursor, featureId)

def upsert_features(cursor, featureIds, featureNames=None):
    """
    Upserts a list of featureIds and optional featureNames into the Features
    table and modifies the Expressions table to expect samples with these
    features.
    :param cursor:
    :param featureIds:
    :param featureNames:
    :return:
    """
    _alter_expressions_table(cursor, featureIds)
    _upsert_features(cursor, featureIds, featureNames)

def upsert_sample(cursor, sampleId, featureIds, values, add_features=True):
    """
    Attempts to add a sample using dynamic columns. The list of features do
    not need to be present in the database.
    :param cursor:
    :param sampleId:    A string that will uniquely identify the Sample.
    :param featureIds:  A list of `featureId` strings that uniquely identify
                        the feature and retains the order of the `values`
                        argument.
    :param values:      A list of numeric values retaining the order of the
                        `featureIds` argument.
    :param add_features:
                        Instructs the function about whether or not the sample
                        is expected to present new features to the database.
    :return cursor:
    """
    if add_features:
        _alter_expressions_table(cursor, featureIds)
        _upsert_features(cursor, featureIds)
    _upsert_sample(cursor, sampleId, featureIds, values)
    return cursor


def upsert_samples(cursor, sampleIds, featureIds, vectors):
    """
    Attempts to upsert a list of expression vectors ordered by the list of
    sampleIds and featureIds provided.
    :param cursor:
    :param sampleIds:
    :param featureIds:
    :param vectors:
    :return:
    """
    _alter_expressions_table(cursor, featureIds)
    _upsert_features(cursor, featureIds)
    for k, sampleId in enumerate(sampleIds):
        _upsert_sample(cursor, sampleId, featureIds, vectors[k])
    return cursor


def connect(url, **kwargs):
    """
    A loose layer over phoenixdb's connect method.
    :param url:
    :return:
    """
    return phoenixdb.connect(url, autocommit=True, **kwargs)


def list_features(cursor, limit=200000, offset=0):
    """
    A convenience function for accessing the list of featureIds from the
    Features table.
    :param cursor:
    :param limit:   Integer value to limit the number of returned featureIds.
    :param offset:  Integer value to offset into the list of features.
                    (useful when the list of features is very long)
    :return:
    """
    cursor.execute("SELECT * from Features "
                   "LIMIT {} OFFSET {}".format(limit, offset))
    return _fetchall_keys(cursor)


def list_samples(cursor, limit=1000000, offset=0):
    """
    A convenience function for accessing the list of sampleIds from the
    Samples table.
    :param cursor:
    :param limit:   Integer value to limit the number of returned sampleIds.
    :param offset:  Integer value to offset into the list of sampleIds.
    :return:
    """
    cursor.execute("SELECT sampleId from Expressions "
                   "LIMIT {} OFFSET {}".format(limit, offset))
    return _fetchall_keys(cursor)


def matrix(cursor, sampleIds, featureIds):
    """
    A convenience function for gathering matrices of expression data from the
    expressions table.
    :param cursor:
    :param sampleIds:   A list of `sampleId` strings for which one would like
                        expression data.
    :param featureIds:  A list of featureId strings for which one would like
                        expression data.
    :return:
    """
    cursor.execute(matrix_sql(sampleIds, featureIds))
    return cursor.fetchall()


def matrix_sql(sampleIds, featureIds):
    """
    A convenience function for generating the request for a sample-feature
    matrix. It includes the sampleId, which simplifies labeling into a
    dataframe. Also used internally by the `matrix` function.
    :param sampleIds:
    :param featureIds:
    :return:
    """
    feature_list = ", ".join(featureIds)
    sample_list = ", ".join(map(lambda x: "'{}'".format(x), sampleIds))
    sql = "SELECT sampleId, {} from Expressions " \
          "WHERE sampleId IN({})".format(
            feature_list, sample_list)
    return sql


def _fetchall_keys(cursor):
    """
    A private convenience function that gets the first item from every row
    of a fetch. This is useful for gathering keys of samples and features.
    :param cursor:
    :return: One dimensional list of first value gathered from a cursor.
    """
    return [x[0] for x in cursor.fetchall()]


def _safe_fn(fn, *args):
    """
    A catch all higher order function for general exception handling.
    :param fn:
    :param args:
    :return:
    """
    ret = None
    try:
        ret = fn(*args)
    except Exception as e:
        print(e)
    return ret


def initialize(connection):
    """
    Initializes the celldb tables using a phoenixdb connection.
    :param connection:
    :return:
    """
    cursor = connection.cursor()
    _safe_fn(_create_expressions_table, cursor)
    _safe_fn(_create_features_table, cursor)
    return cursor
