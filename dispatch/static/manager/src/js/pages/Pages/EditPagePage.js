import React from 'react'

import PageEditor from '../../components/PageEditor'

export default function EditPagePage(props) {
  return (
    <PageEditor
      pageId={props.params.pageId}
      goBack={props.history.goBack}
      location={props.location}
      route={props.route} />
  )
}
