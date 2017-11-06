import AlteryxPythonSDK as Sdk
import xml.etree.ElementTree as Et
import csv
import os


class AyxPlugin:
    """
    Implements the plugin interface methods, to be utilized by the Alteryx engine to communicate with this plugin.
    Prefixed with "pi", the Alteryx engine will expect the below five interface methods to be defined.
    """

    def __init__(self, n_tool_id: int, alteryx_engine: object, output_anchor_mgr: object):
        """
        Constructor is called whenever the Alteryx engine wants to instantiate an instance of this plugin.
        :param n_tool_id: The assigned unique identification for a tool instance.
        :param alteryx_engine: Provides an interface into the Alteryx engine.
        :param output_anchor_mgr: A helper that wraps the outgoing connections for a plugin.
        """

        # Default properties
        self.n_tool_id = n_tool_id
        self.alteryx_engine = alteryx_engine
        self.output_anchor_mgr = output_anchor_mgr

        # Custom properties
        self.file_path = ''
        self.is_initialized = True
        self.output_anchor = None

    def pi_init(self, str_xml: str):
        """
        Handles extracting user-entered file name, and input data verification.
        Called when the Alteryx engine is ready to provide the tool configuration from the GUI.
        :param str_xml: The raw XML from the GUI.
        """

        # Getting the user-entered file name string from the GUI, and the output anchor from the XML file.
        self.file_path = Et.fromstring(str_xml).find('browseFiles').text if 'browseFiles' in str_xml else ''
        self.output_anchor = self.output_anchor_mgr.get_output_anchor('Output')

        if not self.file_path:
            self.display_error_msg('Please specify a csv file')
        elif not self.is_csv():
            self.display_error_msg('This tool only accepts csv files')
        elif not os.path.exists(self.file_path):
            self.display_error_msg('No such file or directory: ' + self.file_path)

    def pi_add_incoming_connection(self, str_type: str, str_name: str) -> object:
        """
        The IncomingInterface objects are instantiated here, one object per incoming connection, however since\
        this tool does not accept an incoming connection, instantiation is not needed.
        Called when the Alteryx engine is attempting to add an incoming data connection.
        :param str_type: The name of the input connection anchor, defined in the Config.xml file.
        :param str_name: The name of the wire, defined by the workflow author.
        :return: self.
        """

        return self

    def pi_add_outgoing_connection(self, str_name: str) -> bool:
        """
        Called when the Alteryx engine is attempting to add an outgoing data connection.
        :param str_name: The name of the output connection anchor, defined in the Config.xml file.
        :return: True signifies that the connection is accepted.
        """

        return True

    def pi_push_all_records(self, n_record_limit: int) -> bool:
        """
        Handles reading in the data from the file, mapping out the layout going out, and pushing records out.
        Called when a tool has no incoming data connection.
        :param n_record_limit: Set it to <0 for no limit, 0 for no records, and >0 to specify the number of records.
        :return: False if there are issues with the input data or if the workflow isn't being ran, otherwise True.
        """

        if not self.is_initialized:
            return False

        if self.alteryx_engine.get_init_var(self.n_tool_id, 'UpdateOnly') == True:
            return False

        record_info_out = Sdk.RecordInfo(self.alteryx_engine)  # A fresh record info object.

        # Creating a read-only file object and a reader object which will iterate over lines in the given file.
        file_out = open(self.file_path, 'r', encoding='utf-8')
        file_reader = csv.reader(file_out)

        try:  # Add metadata info that is passed to tools downstream.
            for field in next(file_reader):
                record_info_out.add_field(field, Sdk.FieldType.v_wstring, 254, 0, 'File: ' + self.file_path, '')
        except:
            self.display_error_msg('Must be a UTF-8 file')
            return False

        self.output_anchor.init(record_info_out)  # Lets the downstream tools know of the outgoing record metadata.
        record_creator = record_info_out.construct_record_creator()  # Creating a new record_creator for the new data.

        # SLOWNESS STARTS HERE ================================================================================

        for record in file_reader:
            for field in enumerate(record):
                record_info_out[field[0]].set_from_string(record_creator, field[1])

            # Asking for a record to push downstream, then resetting the record to prevent unexpected results.
            out_record = record_creator.finalize_record()
            self.output_anchor.push_record(out_record, False)  # False: completed connections will automatically close.
            record_creator.reset()

        # ======================================================================================================

        total_records = str(sum(1 for record in file_reader))  # Naming a reference to display to user.
        self.alteryx_engine.output_message(self.n_tool_id, Sdk.EngineMessageType.info, self.xmsg(total_records) + ' records were read from ' + self.file_path)
        self.output_anchor.close()  # Close outgoing connections.
        return True

    def pi_close(self, b_has_errors: bool):
        """
        Called after all records have been processed.
        :param b_has_errors: Set to true to not do the final processing.
        """

        self.output_anchor.assert_close()  # Checks whether connections were properly closed.

    def is_csv(self):
        """
        A non-interface method, that is responsible for determining whether file is csv or not.
        :return: False if the string literal entered for the file extension is not csv, otherwise True.
        """

        filename, file_extension = os.path.splitext(self.file_path)
        if file_extension.lower() == '.csv':
            return True
        return False

    def display_error_msg(self, msg_string: str):
        """
        A non-interface method, that is responsible for displaying the relevant error message in Designer.
        :param msg_string: The custom error message.
        """

        self.is_initialized = False
        self.alteryx_engine.output_message(self.n_tool_id, Sdk.EngineMessageType.error, self.xmsg(msg_string))

    def xmsg(self, msg_string: str):
        """
        A non-interface, non-operational placeholder for the eventual localization of predefined user-facing strings.
        :param msg_string: The user-facing string.
        :return: msg_string
        """

        return msg_string


class IncomingInterface:
    """
    This class is returned by pi_add_incoming_connection, and it implements the incoming interface methods, to be\
    utilized by the Alteryx engine to communicate with a plugin when processing an incoming connection.
    Prefixed with "ii", the Alteryx engine will expect the below four interface methods to be defined.
    """

    def __init__(self, parent: object):
        """
        Constructor for IncomingInterface.
        :param parent: AyxPlugin
        """

        pass

    def ii_init(self, record_info_in: object) -> bool:
        """
        Called to report changes of the incoming connection's record metadata to the Alteryx engine.
        :param record_info_in: A RecordInfo object for the incoming connection's fields.
        """

        pass

    def ii_push_record(self, in_record: object) -> bool:
        """
        Called when an input record is being sent to the plugin.
        :param in_record: The data for the incoming record.
        """

        pass

    def ii_update_progress(self, d_percent: float):
        """
        Called by the upstream tool to report what percentage of records have been pushed.
        :param d_percent: Value between 0.0 and 1.0.
        """

        pass

    def ii_close(self):
        """
        Called when the incoming connection has finished passing all of its records.
        """

        pass
