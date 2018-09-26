from datetime import datetime

from flask import abort, flash, redirect, render_template, request, url_for
from sqlalchemy.exc import IntegrityError, InternalError
from wtforms import ValidationError


class Controller:
    """Controller base class

    Add routes for specific controller and provide generic RESTful actions.
    """

    def __init__(self, resource_name, base_route, endpoint_suffix,
                 templates_dir, app, config_models):
        """Constructor

        :param str resource_name: Visible name of resource (e.g. 'User')
        :param str base_route: Base route for this controller (e.g. 'users')
        :param str endpoint_suffix: Suffix for route endpoints (e.g. 'user')
        :param str templates_dir: Subdir for resource templates (e.g. 'users')
        :param Flask app: Flask application
        :param ConfigModels config_models: Helper for ORM models
        """
        self.resource_name = resource_name
        self.base_route = base_route
        self.endpoint_suffix = endpoint_suffix
        self.templates_dir = templates_dir
        self.app = app
        self.logger = app.logger
        self.config_models = config_models

        self.add_routes(app)

    def add_routes(self, app):
        """Add routes for this controller.

        :param Flask app: Flask application
        """
        base_route = self.base_route
        suffix = self.endpoint_suffix

        # index
        app.add_url_rule(
            '/%s' % base_route, base_route, self.index, methods=['GET']
        )
        # new
        app.add_url_rule(
            '/%s/new' % base_route, 'new_%s' % suffix, self.new,
            methods=['GET']
        )
        # create
        app.add_url_rule(
            '/%s' % base_route, 'create_%s' % suffix, self.create,
            methods=['POST']
        )
        # edit
        app.add_url_rule(
            '/%s/<int:id>/edit' % base_route, 'edit_%s' % suffix, self.edit,
            methods=['GET']
        )
        # update
        app.add_url_rule(
            '/%s/<int:id>' % base_route, 'update_%s' % suffix, self.update,
            methods=['PUT']
        )
        # delete
        app.add_url_rule(
            '/%s/<int:id>' % base_route, 'destroy_%s' % suffix, self.destroy,
            methods=['DELETE']
        )
        # update or delete
        app.add_url_rule(
            '/%s/<int:id>' % base_route, 'modify_%s' % suffix, self.modify,
            methods=['POST']
        )

    def resource_pkey(self):
        """Return primary key column name for resource table (default: 'id')"""
        return 'id'

    # index

    def resources_for_index(self, session):
        """Return resources list.

        Implement in subclass

        :param Session session: DB session
        """
        raise NotImplementedError

    def index(self):
        """Show resources list."""
        session = self.session()
        resources = self.resources_for_index(session)
        session.close()

        return render_template(
            '%s/index.html' % self.templates_dir, resources=resources,
            endpoint_suffix=self.endpoint_suffix, pkey=self.resource_pkey()
        )

    # new

    def new(self):
        """Show new resource form."""
        template = '%s/form.html' % self.templates_dir
        form = self.create_form()
        title = "Add %s" % self.resource_name
        action = url_for('create_%s' % self.endpoint_suffix)

        return render_template(
            template, title=title, form=form, action=action, method='POST'
        )

    # create

    def create(self):
        """Create new resource."""
        form = self.create_form()
        if form.validate_on_submit():
            try:
                # create and commit resource
                session = self.session()
                self.create_or_update_resources(None, form, session)
                session.commit()
                self.update_config_timestamp(session)
                session.close()
                flash('%s has been created.' % self.resource_name, 'success')

                return redirect(url_for(self.base_route))
            except InternalError as e:
                flash('InternalError: %s' % e.orig, 'error')
            except IntegrityError as e:
                flash('IntegrityError: %s' % e.orig, 'error')
            except ValidationError as e:
                flash('Could not create %s.' %
                      self.resource_name, 'warning')
        else:
            flash('Could not create %s.' % self.resource_name,
                  'warning')

        # show validation errors
        template = '%s/form.html' % self.templates_dir
        title = "Add %s" % self.resource_name
        action = url_for('create_%s' % self.endpoint_suffix)

        return render_template(
            template, title=title, form=form, action=action, method='POST'
        )

    # edit

    def find_resource(self, id, session):
        """Find resource by ID.

        Implement in subclass

        :param int id: Resource ID
        :param Session session: DB session
        """
        raise NotImplementedError

    def edit(self, id):
        """Show edit resource form.

        :param int id: Resource ID
        """
        # find resource
        session = self.session()
        resource = self.find_resource(id, session)

        if resource is not None:
            template = '%s/form.html' % self.templates_dir
            form = self.create_form(resource, True)
            session.close()
            title = "Edit %s" % self.resource_name
            action = url_for('update_%s' % self.endpoint_suffix, id=id)

            return render_template(
                template, title=title, form=form, action=action, method='PUT'
            )
        else:
            # resource not found
            session.close()
            abort(404)

    # update

    def update(self, id):
        """Update existing resource.

        :param int id: Resource ID
        """
        # find resource
        session = self.session()
        resource = self.find_resource(id, session)

        if resource is not None:
            form = self.create_form(resource)
            if form.validate_on_submit():
                try:
                    # update and commit resource
                    self.create_or_update_resources(resource, form, session)
                    session.commit()
                    self.update_config_timestamp(session)
                    session.close()
                    flash('%s has been updated.' % self.resource_name,
                          'success')

                    return redirect(url_for(self.base_route))
                except InternalError as e:
                    flash('InternalError: %s' % e.orig, 'error')
                except IntegrityError as e:
                    flash('IntegrityError: %s' % e.orig, 'error')
                except ValidationError as e:
                    flash('Could not update %s.' %
                          self.resource_name, 'warning')
            else:
                flash('Could not update %s.' %
                      self.resource_name, 'warning')

            session.close()

            # show validation errors
            template = '%s/form.html' % self.templates_dir
            title = "Edit %s" % self.resource_name
            action = url_for('update_%s' % self.endpoint_suffix, id=id)

            return render_template(
                template, title=title, form=form, action=action, method='PUT'
            )
        else:
            # resource not found
            session.close()
            abort(404)

    # destroy

    def destroy_resource(self, resource, session):
        """Delete existing resource in DB.

        :param object resource: Resource object
        :param Session session: DB session
        """
        session.delete(resource)

    def destroy(self, id):
        """Delete existing resource.

        :param int id: Resource ID
        """
        # find resource
        session = self.session()
        resource = self.find_resource(id, session)

        if resource is not None:
            try:
                # update and commit resource
                self.destroy_resource(resource, session)
                session.commit()
                self.update_config_timestamp(session)
                flash('%s has been deleted.' % self.resource_name, 'success')
            except InternalError as e:
                flash('InternalError: %s' % e.orig, 'error')
            except IntegrityError as e:
                flash('IntegrityError: %s' % e.orig, 'error')

            session.close()

            return redirect(url_for(self.base_route))
        else:
            # resource not found
            session.close()
            abort(404)

    def modify(self, id):
        """Workaround for missing PUT and DELETE methods in HTML forms
        using hidden form parameter '_method'.
        """
        method = request.form.get('_method', '').upper()
        if method == 'PUT':
            return self.update(id)
        elif method == 'DELETE':
            return self.destroy(id)
        else:
            abort(405)

    def create_form(self, resource=None, edit_form=False):
        """Return form for resource with fields loaded from DB.

        Implement in subclass

        :param object resource: Optional resource object
        :param bool edit_form: Set if edit form
        """
        raise NotImplementedError

    def create_or_update_resources(self, resource, form, session):
        """Create or update resource in DB.

        Implement in subclass

        :param object resource: Optional resource object (None for create)
        :param FlaskForm form: Form for resource
        :param Session session: DB session
        """
        raise NotImplementedError

    def session(self):
        """Return new session for ConfigDB."""
        return self.config_models.session()

    def raise_validation_error(self, field, msg):
        """Raise ValidationError for a field.

        :param wtforms.fields.Field field: WTForms field
        :param str msg: Validation error message
        """
        error = ValidationError(msg)
        field.errors.append(error)
        raise error

    def update_config_timestamp(self, session):
        """Update timestamp of last config change to current UTC time.

        :param Session session: DB session
        """
        # get first timestamp record
        LastUpdate = self.config_models.model('last_update')
        query = session.query(LastUpdate)
        last_update = query.first()
        if last_update is None:
            # create new timestamp record
            last_update = self.LastUpdate()
            session.add(last_update)

        # update and commit new timestamp
        last_update.updated_at = datetime.utcnow()
        session.commit()

    def update_form_collection(
        self, resource, edit_form, subform, select_field, relation_model,
        collection_attr, id_field, id_attr, name_field, name_attr, session
    ):
        """Helper to update collection subform and select field for resource.

        :param object resource: Optional resource object for edit (e.g. group)
        :param bool edit_form: Set if edit form
        :param FieldList subform: Subform for relations (e.g. form.users)
        :param SelectField select_field: Select field for relations
                                         (e.g. form.user)
        :param object relation_model: ConfigModel for relation (e.g. User)
        :param str collection_attr: Collection attribute for resource
                                    (e.g. 'users_collection')
        :param str id_field: ID field of subform (e.g. 'user_id')
        :param str id_attr: ID attribute of relation model (e.g. 'id')
        :param str name_field: Name field of subform (e.g. 'user_name')
        :param str name_attr: Name attribute of relation model (e.g. 'name')
        :param Session session: DB session
        """
        if edit_form:
            # add collection items for resource on edit
            for item in getattr(resource, collection_attr):
                subform.append_entry({
                    id_field: getattr(item, id_attr),
                    name_field: getattr(item, name_attr)
                })

        # load related resources from DB
        query = session.query(relation_model). \
            order_by(getattr(relation_model, name_attr))
        items = query.all()

        # set choices for collection select field
        select_field.choices = [(0, "")] + [
            (getattr(i, id_attr), getattr(i, name_attr)) for i in items
        ]

    def update_collection(self, collection, subform, id_field, relation_model,
                          id_attr, session):
        """Helper to add or remove relations from a resource collection.

        :param object collection: Collection of resource relations
                                  (e.g. Group.user_collection)
        :param FieldList subform: Subform for relations (e.g. form.users)
        :param str id_field: ID field of subform (e.g. 'user_id')
        :param object relation_model: ConfigModel for relation (e.g. User)
        :param str id_attr: ID attribute of relation model (e.g. 'id')
        :param Session session: DB session
        """
        # lookup for relation of resource
        resource_relations = {}
        for relation in collection:
            resource_relations[relation.id] = relation

        # update relations
        relation_ids = []
        for relation in subform:
            # get relation from ConfigDB
            relation_id = int(relation.data[id_field])
            filter = {id_attr: relation_id}
            query = session.query(relation_model).filter_by(**filter)
            relation = query.first()

            if relation is not None:
                relation_ids.append(relation_id)
                if relation_id not in resource_relations:
                    # add relation to resource
                    collection.append(relation)

        # remove removed relations
        for relation in resource_relations.values():
            if relation.id not in relation_ids:
                # remove relation from resource
                collection.remove(relation)