import os
import json
import psycopg2
import re
import subprocess
import traceback
TIMEOUT_SECONDS = 7200


REPLACE_TOKENS = ['####']

# postgresql operation class
class postSql:
    def __init__(self, host_name, port, user, password, db_name):
        """
        :param host_name:
        :param port:
        :param user:
        :param password:
        :param db_name:
        """
        self.host_name = host_name
        self.port = port
        self.user = user
        self.password = password
        self.db_name = db_name
        self.client = psycopg2.connect(host=self.host_name, port=self.port, user=self.user, password=self.password, database=self.db_name)

    def query(self, sql_command):
        """
        :param sql_command: sql operation code
        :return: all items of sql command. Type: list
        """
        cursor = self.client.cursor()
        cursor.execute(sql_command)
        records = cursor.fetchall()
        return records

    def commit(self):
        """
        :return: record operation informaiton
        """
        self.client.commit()

    def close(self):
        """
        :return: close the operation cursor
        """
        self.client.close()


def exec_command(cmd, work_dir='.', timeout=TIMEOUT_SECONDS):
    """
    :param cmd: exec operation command
    :param work_dir:
    :param timeout:
    :return:
    """
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=work_dir)
    try:
        out, err = p.communicate(timeout=timeout)
        if err:
            return {'error': err}
    except Exception as e:
        return {'error': traceback.format_exc()}
    return {'output': out.strip()}

def clean_version(version_string):
    """
    :param version_string: input version
    :return: cleaned version that delete some special chars, eg. # !
    """
    if re.match('^(\d+)$', version_string):
        version_string += '.0'

        # Replace invalid tokens in the version with a '-'
        # TODO: confirm
    for token in REPLACE_TOKENS:
        version_string = version_string.replace(token, '-')
    return version_string

def check_information_from_path(file_path):
    """
    :param file_path: jar file path
    :return: information of jar file path by Manifest. type: dict. eg: {
            "artifact_id": XXX,
            "version": XXX,
            "group_id": XXX,
            "level": 1,
            "dependencies": []
        }
    """
    file_result = {}
    try:
        cmd = f"unzip -q -c %s META-INF/MANIFEST.MF"%(file_path)
        result = exec_command(cmd)
        if "error" in result:
            return empty_result(file_result)
        lines = str(result.get("output"), "utf-8").split("\n")
        naming_mapping = {
            "implementation-title": "",
            "bundle-name": "",
            "specification-title": "",
            "implementation-version": "",
            "bundle-version": "",
            "specification-version": "",
            "implementation-vendor": "",
            "specification-vendor": "",
            "bundle-vendor": "",
            "main-class":"",
            "manifest-version":""
        }
        for l in lines:
            parts = l.split(":")
            if len(parts) == 2:
                k = str(parts[0]).strip().lower()
                v = str(parts[1]).strip().lower()
                if k in naming_mapping.keys():
                    naming_mapping[k] = v
        lib_name = naming_mapping["specification-title"] or naming_mapping["implementation-title"] or naming_mapping[
            "bundle-name"]
        lib_version = naming_mapping["specification-version"] or naming_mapping["implementation-version"] or \
                      naming_mapping[
                          "bundle-version"] or naming_mapping["manifest-version"]
        lib_vendor = naming_mapping["specification-vendor"] or naming_mapping["implementation-vendor"] or \
                     naming_mapping["bundle-vendor"] or naming_mapping["main-class"]
        if not lib_name:
            #print("no useful info in manifest file, use filename for lib_name, jar=%s" %(file_path))
            lib_name = os.path.basename(file_path)
        file_result = {
            "artifact_id": lib_name,
            "version": clean_version(lib_version),
            "group_id": lib_vendor,
            "level": 1,
            "dependencies": []
        }
        return file_result
    except Exception as e:
        #print(e)
        return empty_result(file_result)

def empty_result(file_result):
    """
    :param file_result:
    :return: empty the input dict. eg {
            "artifact_id": '',
            "version": '',
            "group_id": '',
            "level": 1,
            "dependencies": []
        }
    """
    file_result['group_id'] = ''
    file_result['version'] = ''
    file_result['artifact_id'] = ''
    file_result['level'] = 1
    file_result['dependencies'] = []
    return file_result

def check_interest_file(files, client):
    """
    :param files: information of jar files. eg. {
            "filename": "foo-version.jar",
            "filepath": "/Users/zengfeifan/PycharmProjects/CI-analyzer-reference/efda/java/jars/original-jars/lib/com/foodatabase/foo/version/foo-version.jar",
            "sha1": "FD369423346B2F1525C413E33F8CF95B09C92CBD"
        }
    :param client: postgre_sql
    :return: combine result of DB query and Manifest search.
             type: list(dict)
             eg. [{
      "artifact_id": "jbcrypt",
      "group_id": "org.mindrot",
      "version": "0.3m",
      "level": 1,
      "dependencies": []
    }, ...]
    """
    file_results = []
    for file in files:
        file_result = {}
        file_name = file['filename']
        file_path = file['filepath']
        sha1 = file['sha1']

        ###########step1: check sha1 in DB, found libname and libversion
        sql_sha1 = "select * from scantist_library_version_checksum where (checksum_type = 'sha1' and package_type = 'jar' and checksum = '%s');"%(sha1)
        query_sha1 = client.query(sql_command=sql_sha1)
        if len(query_sha1) == 0:
            print("sha1 doesnot matched in DB %s"%sha1)
            file_results.append(check_information_from_path(file_path))
            continue
        else:
            if len(query_sha1) != 1:
                print("Error in DB, a lib_version_ID has more than one items! table:%s\tlib_version_id:%s" % (
                'scantist_library_version_checksum', sha1))
                file_results.append(empty_result(file_result))
                continue
            library_version_id = query_sha1[0][-1]
            sql_library_version = "select * from scantist_library_version where (id = '%s')" % (library_version_id)
            query_library_version = client.query(sql_command=sql_library_version)
            if len(query_library_version) != 1:
                print("Error in DB, a lib_version_ID has more than one items! table:%s\tlib_version_id:%s" % (
                'scantist_library_version', library_version_id))
                file_results.append(empty_result(file_result))
                continue
            lib_id = query_library_version[0][7]
            version_number = query_library_version[0][3]
            sql_library = "select * from scantist_library where (id = '%s')" % (lib_id)
            query_lib = client.query(sql_library)
            if len(query_library_version) != 1:
                print(
                    "Error in DB, a lib_ID has more than one items! table:%s\tlib_id:%s" % ('scantist_library', lib_id))
                file_results.append(empty_result(file_result))
                continue
            vendor = query_lib[0][5]
            file_result['group_id'] = vendor
            file_result['version'] = version_number
            file_result['artifact_id'] = lib_id
            file_result['level'] = 1
            file_result['dependencies'] = []
        file_results.append(file_result)
    return file_results

def combine_result(json_data, result):
    """
    :param json_data: json
    :param result: json
    :return:
    """
    dependencies = json_data['dependencies']
    for index in result:
        dependencies.append(index)
    json_data["dependencies"] = dependencies
    return json_data

def update_dependency_interest_files(json_data):
    """
    :param json_data: data format as ./input/input.json
    :return: data format as .json_result.json
    you should fill in the information of DB before you call this code.
    """
    files = json_data["files_of_interest"]
    db_host = "XXX"
    db_port = 5432
    db_name = "XXX"
    db_user = "XXX"
    db_password = "XXX"
    client = postSql(db_host, db_port, db_user, db_password, db_name)
    result = check_interest_file(files, client)
    #client.commit()
    client.close()
    return combine_result(json_data, result)

if __name__ == '__main__':
    # the following code are used for debug

    input_json = './input/input.json'
    read_file = open(input_json, "r")
    json_data = json.loads(read_file.read())
    files = json_data["files_of_interest"]
    read_file.close()
    with open(os.path.join(os.getcwd(), 'json_result.json'), 'w') as result_write:
        json.dump(update_dependency_interest_files(json_data), result_write)
