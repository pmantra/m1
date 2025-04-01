import React, { useState } from 'react';
import axios from 'axios';
import { isFinite, isEmpty } from 'lodash';

import '../bootstrap/css/bootstrap.scss';
import '../bootstrap/css/bootstrap-theme.scss';

function VerticalProductAddForm({ verticalId }) {
  const [minutes, setMinutes] = useState('');
  const [price, setPrice] = useState('');
  const [errors, setErrors] = useState({ minutes: false, price: false });
  const [isLoading, setIsLoading] = useState(false);

  const onSubmit = (e) => {
    setIsLoading(true)
    e.preventDefault();
    if (!verticalId) {
      return alert('missing verticalId');
    }

    const parsedMinutes = parseInt(minutes, 10);
    if (!isFinite(parsedMinutes)) {
      return null;
    }

    const parsedPrice = parseFloat(price, 10);
    if (!isFinite(parsedPrice)) {
      return null;
    }

    const productToAdd = {
      minutes: parsedMinutes,
      price: parsedPrice,
    };

    if (
      !window.confirm(
        `Adding product, Minutes: ${productToAdd.minutes} Price: ${productToAdd.price} for all practitioners in vertical ${verticalId}, press OK to continue.`,
      )
    ) {
      return null;
    }

    axios
      .post('/admin/vertical/create_products/', {
        vertical_id: verticalId,
        product: productToAdd,
      })
      .then(({ data }) => {
        alert(`created ${data.count} total products for practitioners in this vertical`);
        window.location.reload();
        setIsLoading(false);
      })
      .catch((err) => {
        alert(`${JSON.stringify(err.response.data)}`);
        window.location.reload();
      });
    return null;
  };

  return (
    <div style={{ marginLeft: '5px' }}>
      <p style={{ padding: '1px', fontWeight: 'bold', cursor: 'default' }}>
        Add Product to Vertical
      </p>
      <form onSubmit={onSubmit} className="form-inline">
        <input
          min="1"
          value={minutes}
          onChange={(e) => {
            setErrors({ ...errors, minutes: !e.target.checkValidity() });
            setMinutes(e.target.value);
          }}
          style={{ height: '30px', width: '100px', marginRight: '3px' }}
          type="number"
          className="input-small"
          placeholder="Length"
        />
        <input
          min="0.1"
          step="0.01"
          value={price}
          onChange={(e) => {
            setErrors({ ...errors, price: !e.target.checkValidity() });
            setPrice(e.target.value);
          }}
          style={{ height: '30px', width: '100px', marginRight: '3px' }}
          type="number"
          className="input-small"
          placeholder="Price"
        />
        <button
          type="submit"
          value="Submit"
          className="btn"
          disabled={errors.price || errors.minutes || !(price && minutes) || isLoading}
        >
          Add
        </button>
      </form>
      {errors.minutes && (
        <div style={{ width: 'fit-content' }} className="alert alert-error">
          Minutes must be a valid.
        </div>
      )}
      {errors.price && (
        <div style={{ width: 'fit-content' }} className="alert alert-error">
          Price must be a valid price.
        </div>
      )}
    </div>
  );
}

function VerticalProductEditor({ args }) {
  const products = isEmpty(args.products) ? [] : args.products;

  const verticalId = args.verticalId || null;

  const handleVerticalProductDeactivate = (productToDeactivate) => {
    if (!verticalId) {
      alert('No veritcal id given, skipping');
      return;
    }

    if (
      !window.confirm(
        `Deactivating products, Minutes: ${productToDeactivate.minutes} Price: ${productToDeactivate.price} for all practitioners in vertical ${verticalId}, press OK to continue.`,
      )
    ) {
      return;
    }

    axios
      .post('/admin/vertical/deactivate_products/', {
        vertical_id: verticalId,
        product: {
          minutes: productToDeactivate.minutes,
          price: productToDeactivate.price,
        },
      })
      .then(({ data }) => {
        alert(`deactivated ${data.count} total products for practitioners in this vertical`);
        window.location.reload();
      })
      .catch((err) => {
        alert(`${JSON.stringify(err.response.data)}`);
        window.location.reload();
      });
  };

  return (
    <div className="container">
      <table className="table table-striped" style={{ width: '30%' }}>
        <thead>
          <tr>
            <th style={{ width: '30%' }}>Mins</th>
            <th style={{ width: '30%' }}>Price</th>
            <th style={{ width: '30%' }}>Count</th>
            <th style={{ width: '10%' }}>Deactivate</th>
          </tr>
        </thead>
        <tbody>
          {products.map((p) => (
            <tr key={p.id}>
              <td>{p.minutes}</td>
              <td>{p.price}</td>
              <td>{p.count}</td>
              <td style={{ textAlign: 'center' }}>
                <i
                  role="button"
                  tabIndex={0}
                  aria-label="glyphicon-remove"
                  onClick={() => handleVerticalProductDeactivate(p)}
                  onKeyDown={() => handleVerticalProductDeactivate(p)}
                  className="glyphicon glyphicon-remove"
                  style={{ cursor: 'pointer' }}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <VerticalProductAddForm verticalId={verticalId} />
    </div>
  );
}

export default VerticalProductEditor;
