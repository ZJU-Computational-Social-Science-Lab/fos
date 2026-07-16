class Action:
    NAME = "base_action"
    INSTRUCTION = ""
    DESC = ""
    REPROMPT_PARAM = None

    def handle(self, action_data, agent, simulator, scene):
        """
        Execute the action.

        Return:
        (success, result, summary, meta, pass_control)
        """
        raise NotImplementedError
