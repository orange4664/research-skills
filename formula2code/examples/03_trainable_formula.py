#!/usr/bin/env python3
"""
formula2code Example 3: Trainable Formula Optimization
========================================================
Use sympytorch to make formula coefficients trainable via gradient descent.
This is useful for:
  - Learning unknown constants in a formula
  - Fine-tuning a formula to fit data
  - Symbolic regression

Official reference: https://github.com/patrick-kidger/sympytorch
"""
try:
    import sympy
    import torch
    import sympytorch

    print("=" * 60)
    print("  Trainable Formula: Learning y = a*sin(x) + b*cos(x)")
    print("=" * 60)

    # Define symbolic expression with learnable coefficients
    x = sympy.symbols('x')
    a, b = 3.0, 2.0  # These become nn.Parameter

    expr_sin = a * sympy.sin(x)
    expr_cos = b * sympy.cos(x)

    # Create module — floats automatically become trainable Parameters!
    mod = sympytorch.SymPyModule(expressions=[expr_sin + expr_cos])

    print(f"\n  Formula: {a}*sin(x) + {b}*cos(x)")
    print(f"  Initial params: {[p.item() for p in mod.parameters()]}")

    # Generate "target" data from the true formula: 5*sin(x) + 1*cos(x)
    x_data = torch.linspace(0, 6.28, 100)
    y_true = 5.0 * torch.sin(x_data) + 1.0 * torch.cos(x_data)

    # Train to find the correct coefficients
    optimizer = torch.optim.Adam(mod.parameters(), lr=0.1)

    for epoch in range(200):
        y_pred = mod(x=x_data).squeeze()
        loss = torch.nn.functional.mse_loss(y_pred, y_true)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        if epoch % 50 == 0 or epoch == 199:
            params = [round(p.item(), 3) for p in mod.parameters()]
            print(f"  Epoch {epoch:3d} | Loss: {loss.item():.6f} | Params: {params}")

    print(f"\n  Learned params: {[round(p.item(), 2) for p in mod.parameters()]}")
    print(f"  True params:    [5.0, 1.0]")

    # Show the updated symbolic expression
    print(f"\n  Updated SymPy expression: {mod.sympy()}")

except ImportError as e:
    print(f"⚠️  Missing dependency: {e}")
    print("Install: pip install sympytorch torch")
