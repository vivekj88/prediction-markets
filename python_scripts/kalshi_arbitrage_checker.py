import pandas as pd

def find_a_b_with_closeness(x, y, max_range=1000):
    """
    Finds values of a and b such that:
    1. x * a >= (a + b) * 100
    2. y * b >= (a + b) * 100
    3. b > a (ensured by the range of b)
    
    Calculates the closest percentages for each solution found.

    Parameters:
        x (int): Value of x, where x > y.
        y (int): Value of y.
        max_range (int): Maximum range to test for a and b.

    Returns:
        dict: A dictionary containing solutions, closest values, and a DataFrame with sorted results.
    """
    solutions = []
    closest_a, closest_b = None, None
    closest_diff_a, closest_diff_b = float('inf'), float('inf')

    for a in range(1, max_range):
        for b in range(a + 1, max_range):  # Ensure b > a
            lhs_a = x * a
            lhs_b = y * b
            rhs = (a + b) * 100

            if lhs_a >= rhs and lhs_b >= rhs:
                percentage_closeness_a = (lhs_b / rhs) * 100
                percentage_closeness_b = (lhs_a / rhs) * 100
                avg_percentage_closeness = (percentage_closeness_a + percentage_closeness_b) / 2
                solutions.append((a, b, lhs_a, lhs_b, rhs, percentage_closeness_a, percentage_closeness_b, avg_percentage_closeness))
            else:
                # Check how close x * a is to (a + b) * 100
                diff_a = abs(lhs_a - rhs)
                if diff_a < closest_diff_a:
                    closest_diff_a = diff_a
                    closest_a = (a, b, lhs_a, lhs_b, rhs, (lhs_b / rhs) * 100)

                # Check how close y * b is to (a + b) * 100
                diff_b = abs(lhs_b - rhs)
                if diff_b < closest_diff_b:
                    closest_diff_b = diff_b
                    closest_b = (a, b, lhs_a, lhs_b, rhs, (lhs_a / rhs) * 100)

    # Create a DataFrame for solutions
    if solutions:
        df = pd.DataFrame(solutions, columns=["a", "b", "x * a", "y * b", "target", 
                                              "percentage_closeness_yb", "percentage_closeness_xa", 
                                              "avg_percentage_closeness"])
        df = df.sort_values(by=["avg_percentage_closeness", "target"], ascending=[False, True]).reset_index(drop=True)
    else:
        df = None

    return {
        "solutions": solutions,
        "closest_a": closest_a,
        "closest_b": closest_b,
        "dataframe": df,
    }


# Input values for x and y
try:
    x = int(input("Enter the value of x (x > y): "))
    y = int(input("Enter the value of y (y < x): "))

    if x <= y:
        print("Error: Ensure that x > y.")
    else:
        # Find solutions or closest values
        max_range = int(input("Enter the maximum range to test for a and b: "))
        result = find_a_b_with_closeness(x, y, max_range)

        # Output solutions
        solutions = result['solutions']
        if solutions:
            print("Solutions for (a, b):")
            for solution in solutions:
                a, b, lhs_a, lhs_b, rhs, percentage_closeness_a, percentage_closeness_b, avg_closeness = solution
                print(f"a = {a}, b = {b}, x * a = {lhs_a}, y * b = {lhs_b}, target = {rhs}, "
                      f"percentage closeness (using y * b) = {percentage_closeness_a:.2f}%, "
                      f"percentage closeness (using x * a) = {percentage_closeness_b:.2f}%, "
                      f"average percentage closeness = {avg_closeness:.2f}%")

            # Display sorted DataFrame
            print("\nSorted DataFrame by Average Percentage Closeness (and Target):")
            print(result['dataframe'])
        else:
            print("No exact solutions found.")

        # Output closest cases
        closest_a = result['closest_a']
        closest_b = result['closest_b']

        print("\nClosest values when no exact solutions found or for comparison:")
        print(f"Closest for x * a: a = {closest_a[0]}, b = {closest_a[1]}, "
              f"x * a = {closest_a[2]}, y * b = {closest_a[3]}, target = {closest_a[4]}, "
              f"percentage closeness (using y * b) = {closest_a[5]:.2f}%")
        print(f"Closest for y * b: a = {closest_b[0]}, b = {closest_b[1]}, "
              f"x * a = {closest_b[2]}, y * b = {closest_b[3]}, target = {closest_b[4]}, "
              f"percentage closeness (using x * a) = {closest_b[5]:.2f}%")
except ValueError:
    print("Error: Please enter valid integers for x and y.")
