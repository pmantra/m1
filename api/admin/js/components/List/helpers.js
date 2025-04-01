import axios from 'axios';
import { isEmpty } from 'lodash';


const filtersToQueryString = (filters=[]) => Object.keys(filters).map(name => `${name  }=${  filters[name]}`).join('&');

export const formatURL = (url, page, search, pageSize=20, filters=[], sort="", desc="") => {
  let formattedURL = `${url}?page=${page}&page_size=${pageSize}`;
  if (!isEmpty(filters)) {
    formattedURL = `${formattedURL}&${filtersToQueryString(filters)}`;
  }

  if (!isEmpty(search)) {
    formattedURL = `${formattedURL}&search=${search}`;
  }

  if (sort !== "") {
    formattedURL = `${formattedURL}&sort=${sort}`;
  }

  if (desc !== "") {
    formattedURL = `${formattedURL}&desc=1`;
  }
    
  return formattedURL;
}

export const fetchData = async (url, page, search, pageSize=20, filters=[], sort="", desc="") => {
  const formattedURL = formatURL(url, page, search, pageSize, filters, sort, desc);
  const { data } = await axios.get(formattedURL);
  return data;
};
