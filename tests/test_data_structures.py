import unittest

from msticpy.analysis.anomalous_sequence.utils.data_structures import StateMatrix

START_TOKEN = "##START##"
END_TOKEN = "##END##"
UNK_TOKEN = "##UNK##"


class TestDataStructures(unittest.TestCase):
    def test_state_matrix(self):
        self.assertRaises(AssertionError, lambda: StateMatrix({"haha": 1}, UNK_TOKEN))
        self.assertRaises(AssertionError, lambda: StateMatrix(dict(), UNK_TOKEN))
        states = {"haha": {"lol": 1, UNK_TOKEN: 1}, UNK_TOKEN: {"hehe": 1}}
        self.assertRaises(AssertionError, lambda: StateMatrix(states, UNK_TOKEN))

        states = {"haha": 2, UNK_TOKEN: 5}
        states_matrix = StateMatrix(states, UNK_TOKEN)
        self.assertEqual(states_matrix["kjfkjhf"], states_matrix[UNK_TOKEN])

        states = {
            "haha": {"hehe": 1, UNK_TOKEN: 4},
            UNK_TOKEN: {UNK_TOKEN: 6, "lol": 78},
        }
        states_matrix = StateMatrix(states, UNK_TOKEN)
        self.assertEqual(
            states_matrix["kidhf"]["kfji"], states_matrix[UNK_TOKEN][UNK_TOKEN]
        )
        self.assertEqual(
            states_matrix["haha"]["kjdff"], states_matrix["haha"][UNK_TOKEN]
        )
        self.assertEqual(states_matrix["haha"]["hehe"], 1)


if __name__ == "__main__":
    unittest.main()
